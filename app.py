from flask import Flask, request, send_file, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from reportlab.pdfgen import canvas
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
    )""")

    db.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        appointment_date TEXT,
        name TEXT,
        patient_type TEXT,
        mobile TEXT UNIQUE,
        city TEXT,
        problem TEXT
    )""")

    db.execute("""
    CREATE TABLE IF NOT EXISTS treatment (
        patient_id INTEGER PRIMARY KEY,
        plan TEXT,
        final_amount INTEGER,
        consultant TEXT,
        lab TEXT
    )""")

    db.execute("""
    CREATE TABLE IF NOT EXISTS treatment_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        treatment_date TEXT,
        notes TEXT
    )""")

    db.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        payment_date TEXT,
        amount INTEGER,
        mode TEXT
    )""")

    db.commit()

def init_admin():
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)",
        ("admin", generate_password_hash("admin123"))
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
    if request.method == "POST":
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=?",
            (request.form["username"],)
        ).fetchone()

        if user and check_password_hash(user[2], request.form["password"]):
            session["user"] = user[1]
            return redirect("/")
        return "Invalid login"

    return """
    <h2>Login</h2>
    <form method="post">
        <input name="username" required><br><br>
        <input type="password" name="password" required><br><br>
        <button>Login</button>
    </form>
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

    if request.method == "POST":
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
            pass

    patients = db.execute("SELECT * FROM patients").fetchall()

    html = """
    <h2>Clinic CRM</h2>
    <a href="/logout">Logout</a><br><br>

    <form method="post">
        <input type="date" name="appointment_date" required><br>
        <input name="name" placeholder="Name" required><br>
        <select name="patient_type"><option>New</option><option>Old</option></select><br>
        <input name="mobile" placeholder="Mobile" required><br>
        <input name="city" placeholder="City" required><br>
        <textarea name="problem" placeholder="Problem" required></textarea><br>
        <button>Add Patient</button>
    </form>

    <h3>Patients</h3>
    """

    for p in patients:
        html += f"<div>{p[2]} | {p[4]} <a href='/patient/{p[0]}'>View</a></div>"

    return html

# ---------------- PATIENT PAGE ----------------
@app.route("/patient/<int:patient_id>", methods=["GET", "POST"])
def patient(patient_id):
    if "user" not in session:
        return redirect("/login")

    db = get_db()

    # Save / Update Final Treatment
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

    # Save Treatment Notes
    if request.method == "POST" and "notes" in request.form:
        db.execute("""
        INSERT INTO treatment_notes (patient_id, treatment_date, notes)
        VALUES (?, ?, ?)
        """, (
            patient_id,
            request.form["treatment_date"],
            request.form["notes"]
        ))
        db.commit()

    # Save Payment
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
    notes = db.execute("SELECT * FROM treatment_notes WHERE patient_id=? ORDER BY treatment_date", (patient_id,)).fetchall()
    payments = db.execute("SELECT * FROM payments WHERE patient_id=?", (patient_id,)).fetchall()

    final_amount = treatment[2] if treatment else 0
    paid = sum(p[3] for p in payments)
    balance = final_amount - paid

    html = f"""
    <h2>{patient[2]}</h2>
    <a href="/">⬅ Back</a><br><br>

    <h3>Final Treatment (Editable)</h3>
    <form method="post">
        <textarea name="plan">{treatment[1] if treatment else ""}</textarea><br>
        <input name="amount" value="{final_amount}"><br>
        <input name="consultant" value="{treatment[3] if treatment else ""}"><br>
        <input name="lab" value="{treatment[4] if treatment else ""}"><br>
        <button>Save Treatment</button>
    </form>

    <h3>Add Treatment Note</h3>
    <form method="post">
        <input type="date" name="treatment_date" required><br>
        <textarea name="notes" required></textarea><br>
        <button>Add Note</button>
    </form>

    <h3>Treatment History</h3>
    """

    for n in notes:
        html += f"<p>{n[2]} : {n[3]}</p>"

    html += """
    <h3>Add Payment</h3>
    <form method="post">
        <input type="date" name="payment_date" required><br>
        <input name="payment_amount" required><br>
        <select name="payment_mode">
            <option>Cash</option>
            <option>UPI</option>
            <option>Card</option>
        </select><br>
        <button>Add Payment</button>
    </form>

    <h3>Payment History</h3>
    """

    for p in payments:
        html += f"<p>{p[2]} | {p[4]} | {p[3]}</p>"

    html += f"""
    <p><b>Total:</b> {final_amount} | <b>Paid:</b> {paid} | <b>Balance:</b> {balance}</p>
    <a href="/invoice/{patient_id}">🧾 Download Invoice</a>
    """

    return html

# ---------------- INVOICE ----------------
@app.route("/invoice/<int:patient_id>")
def invoice(patient_id):
    db = get_db()

    patient = db.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
    treatment = db.execute("SELECT * FROM treatment WHERE patient_id=?", (patient_id,)).fetchone()
    notes = db.execute("SELECT * FROM treatment_notes WHERE patient_id=? ORDER BY treatment_date", (patient_id,)).fetchall()
    payments = db.execute("SELECT * FROM payments WHERE patient_id=?", (patient_id,)).fetchall()

    final_amount = treatment[2] if treatment else 0
    paid = sum(p[3] for p in payments)
    balance = final_amount - paid

    file_name = f"invoice_{patient_id}.pdf"
    pdf = canvas.Canvas(file_name)

    y = 800
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Dr C Krishnarjuna Rao's Dental Clinic")

    y -= 30
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Patient: {patient[2]}")

    y -= 20
    pdf.drawString(50, y, f"Treatment Plan: {treatment[1] if treatment else ''}")

    y -= 30
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Treatment History")
    y -= 15

    pdf.setFont("Helvetica", 10)
    for n in notes:
        pdf.drawString(50, y, f"{n[2]} - {n[3]}")
        y -= 14

    y -= 20
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Payment History")
    y -= 15

    pdf.setFont("Helvetica", 10)
    for p in payments:
        pdf.drawString(50, y, f"{p[2]} | {p[4]} | {p[3]}")
        y -= 14

    y -= 20
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, f"Total: {final_amount}  Paid: {paid}  Balance: {balance}")

    pdf.save()
    return send_file(file_name, as_attachment=True)

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
