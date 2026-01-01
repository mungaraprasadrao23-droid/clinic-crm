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

    db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

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

    db.execute("""
    CREATE TABLE IF NOT EXISTS treatment (
        patient_id INTEGER PRIMARY KEY,
        plan TEXT,
        final_amount INTEGER,
        consultant TEXT,
        lab TEXT
    )
    """)

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
        <input name="username" placeholder="Username" required><br><br>
        <input type="password" name="password" placeholder="Password" required><br><br>
        <button>Login</button>
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
        try:
            db.execute("""
                INSERT INTO patients
                (appointment_date, name, patient_type, mobile, city, problem)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                request.form["appointment_date"],
                request.form["name"],
                request.form["patient_type"],
                request.form["mobile"],
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
        <input type="date" name="appointment_date" required><br><br>
        <input name="name" placeholder="Name" required><br><br>
        <select name="patient_type">
            <option>New</option>
            <option>Old</option>
        </select><br><br>
        <input name="mobile" placeholder="Mobile" required><br><br>
        <input name="city" placeholder="City" required><br><br>
        <textarea name="problem" placeholder="Problem" required></textarea><br><br>
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
    <a href="/">⬅ Back</a><br><br>

    <h3>Treatment</h3>
    <form method="post">
        <textarea name="plan">{treatment[1] if treatment else ""}</textarea><br><br>
        <input name="amount" value="{final_amount}"><br><br>
        <input name="consultant" placeholder="Consultant"><br><br>
        <input name="lab" placeholder="Lab"><br><br>
        <button>Save Treatment</button>
    </form>

    <h3>Add Payment</h3>
    <form method="post">
        <input type="date" name="payment_date" required><br><br>
        <input name="payment_amount" required><br><br>
        <select name="payment_mode">
            <option>Cash</option>
            <option>UPI</option>
            <option>Card</option>
        </select><br><br>
        <button>Add Payment</button>
    </form>

    <p>Total: {final_amount} | Paid: {total_paid} | Balance: {balance}</p>
    <a href="/invoice/{patient_id}">🧾 Download Invoice</a>
    """
    return html


# ---------------- INVOICE ----------------
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
    pdf = canvas.Canvas(file_name, pagesize=(595, 842))  # A4

    PAGE_WIDTH = 595
    PAGE_HEIGHT = 842
    LEFT = 40
    RIGHT = PAGE_WIDTH - 40
    TOP = PAGE_HEIGHT - 40
    BOTTOM = 40

    # -------- HEADER --------
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(PAGE_WIDTH / 2, TOP, "TREATMENT INVOICE")

    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(PAGE_WIDTH / 2, TOP - 22, "Dr C Krishnarjuna Rao's Dental Clinic")
    pdf.drawCentredString(
        PAGE_WIDTH / 2,
        TOP - 38,
        "Krishna Nagar 2nd Lane, Opp NTR Statue, Guntur – 522006 | Ph: 7794922294"
    )

    pdf.line(LEFT, TOP - 50, RIGHT, TOP - 50)

    # -------- PATIENT DETAILS --------
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(LEFT, TOP - 75, "Patient Details")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(LEFT, TOP - 95, f"Patient Name : {patient[2]}")
    pdf.drawString(LEFT, TOP - 110, f"Mobile       : {patient[4]}")
    pdf.drawString(LEFT, TOP - 125, f"City         : {patient[5]}")
    pdf.drawString(LEFT, TOP - 140, f"Problem      : {patient[6]}")

    # -------- TREATMENT DETAILS --------
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(LEFT, TOP - 165, "Treatment Details")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(LEFT, TOP - 185, f"Treatment Plan : {treatment[1] if treatment else ''}")
    pdf.drawString(LEFT, TOP - 200, f"Consultant     : {treatment[3] if treatment else ''}")
    pdf.drawString(LEFT, TOP - 215, f"Lab Incharge   : {treatment[4] if treatment else ''}")
    pdf.drawString(LEFT, TOP - 230, f"Final Amount   : {final_amount}")

    # -------- PAYMENTS TABLE --------
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(LEFT, TOP - 260, "Payment Details")

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(LEFT, TOP - 280, "Date")
    pdf.drawString(LEFT + 200, TOP - 280, "Mode")
    pdf.drawRightString(RIGHT, TOP - 280, "Amount")

    pdf.line(LEFT, TOP - 285, RIGHT, TOP - 285)

    pdf.setFont("Helvetica", 10)
    y = TOP - 300

    for p in payments:
        pdf.drawString(LEFT, y, p[2])
        pdf.drawString(LEFT + 200, y, p[4])
        pdf.drawRightString(RIGHT, y, str(p[3]))
        y -= 18

    # -------- TOTALS --------
    pdf.line(RIGHT - 200, y - 5, RIGHT, y - 5)

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawRightString(RIGHT, y - 25, f"Total Amount : {final_amount}")
    pdf.drawRightString(RIGHT, y - 40, f"Total Paid   : {total_paid}")
    pdf.drawRightString(RIGHT, y - 55, f"Balance      : {balance}")

    # -------- FOOTER --------
    pdf.line(LEFT, BOTTOM + 30, RIGHT, BOTTOM + 30)

    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(
        PAGE_WIDTH / 2,
        BOTTOM + 15,
        "Thank you for visiting our clinic. Get well soon!"
    )

    pdf.save()
    return send_file(file_name, as_attachment=True)

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
