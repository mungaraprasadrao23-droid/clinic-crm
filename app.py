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


# ---------------- CREATE FIRST USER ----------------
@app.route("/create-user")
def create_user():
    db = get_db()
    hashed_password = generate_password_hash("admin123")
    db.execute(
        "INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)",
        ("admin", hashed_password)
    )
    db.commit()
    return "Admin user created securely. Username: admin | Password: admin123"

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
    <h2>Clinic Login</h2>
    <form method="post">
        Username:<br>
        <input name="username" required><br><br>
        Password:<br>
        <input type="password" name="password" required><br><br>
        <button type="submit">Login</button>
    </form>
    <p style="color:red;">{error}</p>
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
            error = "Mobile number already exists"
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
    <h2>Clinic CRM</h2>
    <a href="/logout">Logout</a><br><br>

    <h3>Search Patient</h3>
    <form method="post">
        <input name="search_mobile" placeholder="Mobile" required>
        <button>Search</button>
    </form>
    <p style="color:red;">{error}</p>

    <hr>
    <h3>Add Patient</h3>
    <form method="post">
        Date: <input type="date" name="appointment_date" required><br><br>
        Name: <input name="name" required><br><br>
        Type:
        <select name="patient_type">
            <option>New</option>
            <option>Old</option>
        </select><br><br>
        Mobile: <input name="mobile" required><br><br>
        City: <input name="city" required><br><br>
        Problem:<br>
        <textarea name="problem" required></textarea><br><br>
        <button>Save</button>
    </form>

    <hr>
    <h3>Patient List</h3>
    """

    for p in patients:
        html += f"{p[0]} | {p[2]} | {p[4]} <a href='/patient/{p[0]}'>View</a><br>"

    html += "<br><a href='/export_patients'>Export Excel</a>"
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

    html = f"""
    <h2>{patient[2]}</h2>
    <a href="/">Back</a><br><br>

    <h3>Treatment</h3>
    <form method="post">
        <textarea name="plan">{treatment[1] if treatment else ""}</textarea><br>
        Amount: <input name="amount" value="{final_amount}"><br>
        Consultant: <input name="consultant"><br>
        Lab: <input name="lab"><br>
        <button>Save</button>
    </form>

    <h3>Add Payment</h3>
    <form method="post">
        <input type="date" name="payment_date" required>
        <input name="payment_amount" required>
        <select name="payment_mode">
            <option>Cash</option>
            <option>UPI</option>
            <option>Card</option>
        </select>
        <button>Add</button>
    </form>

    <hr>
    Total: {final_amount}<br>
    Paid: {total_paid}<br>
    Balance: {balance}<br><br>

    <a href="/invoice/{patient_id}">Download Invoice</a>
    """
    return html


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
