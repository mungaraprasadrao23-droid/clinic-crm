from flask import Flask, request, send_file, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from reportlab.pdfgen import canvas
from openpyxl import Workbook
from datetime import datetime
import os

# ---------------- DATABASE ----------------
def get_db():
    return sqlite3.connect("clinic.db")


def init_users():
    db = get_db()
    db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)
    db.commit()


# ---------------- APP ----------------
app = Flask(__name__)
app.secret_key = "clinic-secret-key"
init_users()


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        if user and check_password_hash(user[2], password):
            session["user"] = username
            return redirect("/")
        else:
            error = "Invalid username or password"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    body {{
        font-family: Arial;
        background: #f4f6f8;
        padding: 20px;
    }}
    .box {{
        max-width: 400px;
        margin: auto;
        background: white;
        padding: 20px;
        border-radius: 8px;
    }}
    input, button {{
        width: 100%;
        padding: 14px;
        margin-top: 10px;
        font-size: 16px;
    }}
    button {{
        background: #007bff;
        color: white;
        border: none;
        border-radius: 6px;
    }}
    </style>
    </head>
    <body>
    <div class="box">
        <h2 style="text-align:center;">Clinic Login</h2>
        <form method="post">
            <input name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button>Login</button>
        </form>
        <p style="color:red; text-align:center;">{error}</p>
    </div>
    </body>
    </html>
    """


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------- HOME ----------------
@app.route("/", methods=["GET", "POST"])
def home():
    if "user" not in session:
        return redirect("/login")

    db = get_db()
    error = ""

    # SEARCH
    if request.method == "POST" and "search_mobile" in request.form:
        patient = db.execute(
            "SELECT id FROM patients WHERE mobile=?",
            (request.form["search_mobile"],)
        ).fetchone()

        if patient:
            return redirect(f"/patient/{patient[0]}")
        else:
            error = "No patient found"

    # ADD PATIENT
    if request.method == "POST" and "mobile" in request.form:
        mobile = request.form["mobile"]
        existing = db.execute(
            "SELECT id FROM patients WHERE mobile=?",
            (mobile,)
        ).fetchone()

        if existing:
            error = "Mobile already exists"
        else:
            db.execute("""
                INSERT INTO patients
                (appointment_date, name, patient_type, mobile, city, problem)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                request.form["appointment_date"],
                request.form["name"],
                request.form["patient_type"],
                mobile,
                request.form["city"],
                request.form["problem"]
            ))
            db.commit()

    patients = db.execute("SELECT * FROM patients").fetchall()

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    body {{
        font-family: Arial;
        background: #f4f6f8;
        padding: 10px;
    }}
    .container {{
        max-width: 500px;
        margin: auto;
        background: white;
        padding: 15px;
        border-radius: 8px;
    }}
    h2, h3 {{
        text-align: center;
    }}
    input, select, textarea, button {{
        width: 100%;
        padding: 14px;
        margin-top: 8px;
        margin-bottom: 12px;
        font-size: 16px;
    }}
    button {{
        background: #007bff;
        color: white;
        border: none;
        border-radius: 6px;
    }}
    .patient {{
        padding: 10px;
        border-bottom: 1px solid #ddd;
    }}
    a {{
        display: block;
        text-align: center;
        margin-top: 10px;
    }}
    </style>
    </head>
    <body>
    <div class="container">

    <h2>Clinic CRM</h2>
    <a href="/logout">Logout</a>

    <h3>Search Patient</h3>
    <form method="post">
        <input name="search_mobile" placeholder="Mobile Number" required>
        <button>Search</button>
    </form>
    <p style="color:red; text-align:center;">{error}</p>

    <h3>Add Patient</h3>
    <form method="post">
        <input type="date" name="appointment_date" required>
        <input name="name" placeholder="Name" required>
        <select name="patient_type">
            <option>New</option>
            <option>Old</option>
        </select>
        <input name="mobile" placeholder="Mobile" required>
        <input name="city" placeholder="City" required>
        <textarea name="problem" placeholder="Problem" required></textarea>
        <button>Save Patient</button>
    </form>

    <h3>Patient List</h3>
    """

    for p in patients:
        html += f"""
        <div class="patient">
            <b>{p[2]}</b><br>
            Mobile: {p[4]}<br>
            <a href="/patient/{p[0]}">View Patient</a>
        </div>
        """

    html += """
    <a href="/export_patients">Export Excel</a>
    </div>
    </body>
    </html>
    """
    return html


# ---------------- PATIENT ----------------
@app.route("/patient/<int:patient_id>", methods=["GET", "POST"])
def patient(patient_id):
    if "user" not in session:
        return redirect("/login")

    db = get_db()

    if request.method == "POST" and "plan" in request.form:
        db.execute("""
        INSERT OR REPLACE INTO treatment
        (patient_id, plan, final_amount, consultant, lab)
        VALUES (?, ?, ?, ?, ?)
        """, (
            patient_id,
            request.form["plan"],
            request.form["amount"],
            request.form["consultant"],
            request.form["lab"]
        ))
        db.commit()

    if request.method == "POST" and "payment_amount" in request.form:
        db.execute("""
        INSERT INTO payments (patient_id, payment_date, amount, mode)
        VALUES (?, ?, ?, ?)
        """, (
            patient_id,
            request.form["payment_date"],
            request.form["payment_amount"],
            request.form["payment_mode"]
        ))
        db.commit()

    patient = db.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
    treatment = db.execute("SELECT * FROM treatment WHERE patient_id=?", (patient_id,)).fetchone()
    payments = db.execute("SELECT * FROM payments WHERE patient_id=?", (patient_id,)).fetchall()

    final_amount = treatment[2] if treatment else 0
    total_paid = sum(p[3] for p in payments) if payments else 0
    balance = final_amount - total_paid

    return f"""
    <h2>{patient[2]}</h2>
    <a href="/">Back</a><br><br>

    <form method="post">
        <textarea name="plan">{treatment[1] if treatment else ""}</textarea>
        <input name="amount" value="{final_amount}">
        <input name="consultant" placeholder="Consultant">
        <input name="lab" placeholder="Lab">
        <button>Save Treatment</button>
    </form>

    <form method="post">
        <input type="date" name="payment_date" required>
        <input name="payment_amount" required>
        <select name="payment_mode">
            <option>Cash</option>
            <option>UPI</option>
            <option>Card</option>
        </select>
        <button>Add Payment</button>
    </form>

    <p>Total: {final_amount} | Paid: {total_paid} | Balance: {balance}</p>
    <a href="/invoice/{patient_id}">Download Invoice</a>
    """


# ---------------- INVOICE ----------------
@app.route("/invoice/<int:patient_id>")
def invoice(patient_id):
    db = get_db()
    patient = db.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
    treatment = db.execute("SELECT * FROM treatment WHERE patient_id=?", (patient_id,)).fetchone()
    payments = db.execute("SELECT * FROM payments WHERE patient_id=?", (patient_id,)).fetchall()

    total_paid = sum(p[3] for p in payments) if payments else 0
    balance = treatment[2] - total_paid

    file_name = f"invoice_{patient_id}.pdf"
    pdf = canvas.Canvas(file_name)
    pdf.drawString(50, 800, "Clinic Invoice")
    pdf.drawString(50, 770, f"Patient: {patient[2]}")
    pdf.drawString(50, 750, f"Total: {treatment[2]}")
    pdf.drawString(50, 730, f"Paid: {total_paid}")
    pdf.drawString(50, 710, f"Balance: {balance}")
    pdf.save()

    return send_file(file_name, as_attachment=True)


# ---------------- EXPORT ----------------
@app.route("/export_patients")
def export_patients():
    db = get_db()
    patients = db.execute("SELECT id, appointment_date, name, mobile, city FROM patients").fetchall()

    wb = Workbook()
    ws = wb.active
    ws.append(["Date", "Name", "Mobile", "City", "Total", "Paid", "Balance"])

    for p in patients:
        pid = p[0]
        t = db.execute("SELECT final_amount FROM treatment WHERE patient_id=?", (pid,)).fetchone()
        pay = db.execute("SELECT SUM(amount) FROM payments WHERE patient_id=?", (pid,)).fetchone()
        total = t[0] if t else 0
        paid = pay[0] if pay[0] else 0
        ws.append([p[1], p[2], p[3], p[4], total, paid, total - paid])

    fname = f"patients_{datetime.now().date()}.xlsx"
    wb.save(fname)
    return send_file(fname, as_attachment=True)


# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
