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


def init_db():
    db = get_db()

    # USERS
    db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    # PATIENTS
    db.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        appointment_date TEXT,
        name TEXT,
        patient_type TEXT,
        mobile TEXT UNIQUE,
        city TEXT,
        problem TEXT
    )
    """)

    # TREATMENT
    db.execute("""
    CREATE TABLE IF NOT EXISTS treatment (
        patient_id INTEGER PRIMARY KEY,
        plan TEXT,
        final_amount INTEGER,
        consultant TEXT,
        lab TEXT
    )
    """)

    # PAYMENTS
    db.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        payment_date TEXT,
        amount INTEGER,
        mode TEXT
    )
    """)

    db.commit()


def init_admin():
    db = get_db()
    hashed = generate_password_hash("admin123")
    db.execute(
        "INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)",
        ("admin", hashed)
    )
    db.commit()


# ---------------- INIT ----------------
init_db()
init_admin()

# ---------------- APP ----------------
app = Flask(__name__)
app.secret_key = "clinic-secret-key"


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        db = get_db()
        user = db.execute(
            "SELECT id, username, password FROM users WHERE username=?",
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
    body {{ font-family: Arial; background:#f4f6f8; padding:20px; }}
    .box {{ max-width:400px; margin:auto; background:white; padding:20px; border-radius:8px; }}
    input,button {{ width:100%; padding:14px; margin-top:10px; font-size:16px; }}
    button {{ background:#007bff; color:white; border:none; border-radius:6px; }}
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

    if request.method == "POST" and "search_mobile" in request.form:
        patient = db.execute(
            "SELECT id FROM patients WHERE mobile=?",
            (request.form["search_mobile"],)
        ).fetchone()
        if patient:
            return redirect(f"/patient/{patient[0]}")
        else:
            error = "No patient found"

    if request.method == "POST" and "mobile" in request.form:
        mobile = request.form["mobile"]
        try:
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
        except:
            error = "Mobile already exists"

    patients = db.execute("SELECT * FROM patients").fetchall()

    html = f"""
    <h2>Clinic CRM</h2>
    <a href="/logout">Logout</a><br><br>

    <form method="post">
        <input name="search_mobile" placeholder="Search Mobile" required>
        <button>Search</button>
    </form>
    <p style="color:red;">{error}</p>

    <form method="post">
        <input type="date" name="appointment_date" required>
        <input name="name" placeholder="Name" required>
        <select name="patient_type"><option>New</option><option>Old</option></select>
        <input name="mobile" placeholder="Mobile" required>
        <input name="city" placeholder="City" required>
        <textarea name="problem" placeholder="Problem" required></textarea>
        <button>Add Patient</button>
    </form>

    <h3>Patients</h3>
    """

    for p in patients:
        html += f"""
        <div>
            <b>{p[2]}</b> | {p[4]}
            <a href="/patient/{p[0]}">View</a>
        </div>
        """

    html += "<br><a href='/export_patients'>Export Excel</a>"
    return html
    # ---------------- PATIENT PAGE ----------------
@app.route("/patient/<int:patient_id>", methods=["GET", "POST"])
def patient(patient_id):
    if "user" not in session:
        return redirect("/login")

    db = get_db()

    # SAVE TREATMENT
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

    # SAVE PAYMENT
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

    patient = db.execute(
        "SELECT * FROM patients WHERE id=?",
        (patient_id,)
    ).fetchone()

    treatment = db.execute(
        "SELECT * FROM treatment WHERE patient_id=?",
        (patient_id,)
    ).fetchone()

    payments = db.execute(
        "SELECT * FROM payments WHERE patient_id=?",
        (patient_id,)
    ).fetchall()

    final_amount = treatment[2] if treatment else 0
    total_paid = sum(p[3] for p in payments) if payments else 0
    balance = final_amount - total_paid

    html = f"""
    <h2>Patient: {patient[2]}</h2>
    <a href="/">⬅ Back</a><br><br>

    <h3>Treatment</h3>
    <form method="post">
        <textarea name="plan" placeholder="Treatment Plan">{treatment[1] if treatment else ""}</textarea><br><br>
        Final Amount:<br>
        <input name="amount" value="{final_amount}"><br><br>
        Consultant:<br>
        <input name="consultant"><br><br>
        Lab:<br>
        <input name="lab"><br><br>
        <button type="submit">Save Treatment</button>
    </form>

    <hr>

    <h3>Add Payment</h3>
    <form method="post">
        Date:<br>
        <input type="date" name="payment_date" required><br><br>
        Amount:<br>
        <input name="payment_amount" required><br><br>
        Mode:<br>
        <select name="payment_mode">
            <option>Cash</option>
            <option>UPI</option>
            <option>Card</option>
        </select><br><br>
        <button type="submit">Add Payment</button>
    </form>

    <h3>Payments</h3>
    """

    for p in payments:
        html += f"{p[2]} | {p[3]} | {p[4]}<br>"

    html += f"""
    <hr>
    <b>Total Amount:</b> {final_amount}<br>
    <b>Total Paid:</b> {total_paid}<br>
    <b>Balance:</b> {balance}<br><br>

    <a href="/invoice/{patient_id}">🧾 Download Invoice</a>
    """

    return html
# ---------------- PROFESSIONAL INVOICE (PDF) ----------------
@app.route("/invoice/<int:patient_id>")
def invoice(patient_id):
    if "user" not in session:
        return redirect("/login")

    db = get_db()

    patient = db.execute(
        "SELECT * FROM patients WHERE id=?",
        (patient_id,)
    ).fetchone()

    treatment = db.execute(
        "SELECT * FROM treatment WHERE patient_id=?",
        (patient_id,)
    ).fetchone()

    payments = db.execute(
        "SELECT * FROM payments WHERE patient_id=?",
        (patient_id,)
    ).fetchall()

    final_amount = treatment[2] if treatment else 0
    total_paid = sum(p[3] for p in payments) if payments else 0
    balance = final_amount - total_paid

    file_name = f"invoice_{patient_id}.pdf"
    pdf = canvas.Canvas(file_name, pagesize=(595, 842))  # A4 size
    PAGE_WIDTH, PAGE_HEIGHT = 595, 842
LEFT_MARGIN = 50
RIGHT_MARGIN = PAGE_WIDTH - 50
TOP_MARGIN = PAGE_HEIGHT - 50
BOTTOM_MARGIN = 50

    # ---------- HEADER ----------
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(PAGE_WIDTH / 2, TOP_MARGIN, "TREATMENT INVOICE")

    pdf.drawCentredString(PAGE_WIDTH / 2, TOP_MARGIN - 18, "Dr C Krishnarjuna Rao's Dental Clinic")
    pdf.drawCentredString(PAGE_WIDTH / 2, TOP_MARGIN - 34, "Krishna Nagar 2nd Lane, Opp NTR Statue, Guntur – 522006")
    pdf.drawCentredString(PAGE_WIDTH / 2, TOP_MARGIN - 50, "Phone: 7794922294")


    pdf.line(40, 750, 555, 750)

    # ---------- PATIENT DETAILS ----------
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(40, 725, "Patient Details")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, 705, f"Patient Name : {patient[2]}")
    pdf.drawString(40, 690, f"Mobile       : {patient[4]}")
    pdf.drawString(40, 675, f"City         : {patient[5]}")
    pdf.drawString(40, 660, f"Problem      : {patient[6]}")

    # ---------- TREATMENT DETAILS ----------
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(40, 630, "Treatment Details")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, 610, f"Treatment Plan : {treatment[1] if treatment else ''}")
    pdf.drawString(40, 595, f"Consultant     : {treatment[3] if treatment else ''}")
    pdf.drawString(40, 580, f"Lab Incharge   : {treatment[4] if treatment else ''}")
    pdf.drawString(40, 565, f"Final Amount   : {final_amount}")

    # ---------- PAYMENTS TABLE ----------
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(40, 535, "Payment Details")

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, 515, "Date")
    pdf.drawString(220, 515, "Mode")
    pdf.drawString(400, 515, "Amount")
    pdf.line(40, 510, 555, 510)

    pdf.setFont("Helvetica", 10)
    y = 495
    for p in payments:
        pdf.drawString(40, y, p[2])
        pdf.drawString(220, y, p[4])
        pdf.drawRightString(520, y, str(p[3]))
        y -= 18

    # ---------- TOTALS ----------
    pdf.line(300, y - 5, 555, y - 5)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawRightString(520, y - 25, f"Total Amount : {final_amount}")
    pdf.drawRightString(520, y - 40, f"Total Paid   : {total_paid}")
    pdf.drawRightString(520, y - 55, f"Balance      : {balance}")

    # ---------- FOOTER ----------
    pdf.line(40, 90, 555, 90)
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(PAGE_WIDTH / 2, BOTTOM_MARGIN - 10, "Thank you for visiting our clinic. Get well soon!")

    pdf.save()
    return send_file(file_name, as_attachment=True)



# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
