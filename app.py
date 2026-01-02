from flask import Flask, request, send_file, redirect, session, render_template
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from reportlab.pdfgen import canvas
from openpyxl import Workbook
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

    html += """
    <br><br>
    <a href='/export_patients'>Export Patients Summary</a><br>
    <a href='/export_payments'>Export All Payments</a><br>
    <a href='/export_payments_date'>Export Payments (Date Wise)</a>
    """

    return html

# ---------------- PATIENT ----------------
@app.route("/patient/<int:patient_id>", methods=["GET", "POST"])
def patient(patient_id):
    if "user" not in session:
        return redirect("/login")

    db = get_db()

    patient = db.execute(
        "SELECT * FROM patients WHERE id=?", (patient_id,)
    ).fetchone()

    treatment = db.execute(
        "SELECT * FROM treatment WHERE patient_id=?", (patient_id,)
    ).fetchone()

    payments = db.execute(
        "SELECT * FROM payments WHERE patient_id=?", (patient_id,)
    ).fetchall()

    final_amount = treatment[2] if treatment else 0
    total_paid = sum(p[3] for p in payments) if payments else 0
    balance = final_amount - total_paid

    html = f"""
    <h2>{patient[2]}</h2>
    <a href="/">⬅ Back</a><br><br>

    <h3>Treatment Details</h3>
    <p><b>Treatment Plan:</b> {treatment[1] if treatment else 'Not added'}</p>
    <p><b>Final Amount:</b> {final_amount}</p>
    <p><b>Consultant:</b> {treatment[3] if treatment else ''}</p>
    <p><b>Lab:</b> {treatment[4] if treatment else ''}</p>

    <h3>Payment History</h3>
    <table border="1" cellpadding="6">
    <tr>
        <th>Date</th>
        <th>Mode</th>
        <th>Amount</th>
    </tr>
    """

    for p in payments:
        html += f"""
        <tr>
            <td>{p[2]}</td>
            <td>{p[4]}</td>
            <td>{p[3]}</td>
        </tr>
        """

    html += f"""
    </table>
    <br>

    <p>
    <b>Total:</b> {final_amount}<br>
    <b>Paid:</b> {total_paid}<br>
    <b>Balance:</b> {balance}
    </p>

    <a href="/invoice/{patient_id}">🧾 Download Invoice</a>
    """

    return html

# ---------------- INVOICE ----------------
@app.route("/invoice/<int:patient_id>")
def invoice(patient_id):
    if "user" not in session:
        return redirect("/login")

    db = get_db()
    patient = db.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
    treatment = db.execute("SELECT * FROM treatment WHERE patient_id=?", (patient_id,)).fetchone()
    payments = db.execute("SELECT * FROM payments WHERE patient_id=?", (patient_id,)).fetchall()

    final_amount = treatment[2] if treatment else 0
    total_paid = sum(p[3] for p in payments) if payments else 0
    balance = final_amount - total_paid

    file_name = f"invoice_{patient_id}.pdf"
    pdf = canvas.Canvas(file_name, pagesize=(595, 842))

    LEFT, RIGHT, TOP = 40, 555, 802

    # -------- LETTERHEAD --------
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawCentredString(297, TOP, "Dr C Krishnarjuna Rao's Dental Clinic")

    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(297, TOP - 22, "Krishna Nagar 2nd Lane, Opp NTR Statue, Guntur – 522006")
    pdf.drawCentredString(297, TOP - 36, "Phone: 7794922294 | Timings: Mon–Sat 10:30 AM – 1:30 PM & 5:30 PM – 8:30 PM")

    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawCentredString(297, TOP - 52, "60+ Years of Dental Excellence")

    pdf.line(LEFT, TOP - 60, RIGHT, TOP - 60)

    y = TOP - 90

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(LEFT, y, "Patient Details")
    y -= 20

    pdf.setFont("Helvetica", 10)
    pdf.drawString(LEFT, y, f"Name: {patient[2]}")
    y -= 15
    pdf.drawString(LEFT, y, f"Mobile: {patient[4]}")
    y -= 15
    pdf.drawString(LEFT, y, f"City: {patient[5]}")
    y -= 15
    pdf.drawString(LEFT, y, f"Problem: {patient[6]}")

    pdf.save()
    return send_file(file_name, as_attachment=True)

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
