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

from flask import Flask, request, send_file, redirect
import sqlite3
from reportlab.pdfgen import canvas

app = Flask(__name__)
init_users()


def get_db():
    return sqlite3.connect("clinic.db")


# ---------------- HOME PAGE ----------------
@app.route("/", methods=["GET", "POST"])
def home():
    db = get_db()
    error = ""

    # 🔍 SEARCH BY MOBILE
    if request.method == "POST" and "search_mobile" in request.form:
        search_mobile = request.form["search_mobile"]

        patient = db.execute(
            "SELECT id FROM patients WHERE mobile=?",
            (search_mobile,)
        ).fetchone()

        if patient:
            return redirect(f"/patient/{patient[0]}")
        else:
            error = "❌ No patient found with this mobile number"

    # ➕ ADD NEW PATIENT
    if request.method == "POST" and "mobile" in request.form:
        mobile = request.form["mobile"]

        existing = db.execute(
            "SELECT id, name FROM patients WHERE mobile=?",
            (mobile,)
        ).fetchone()

        if existing:
            error = f"⚠️ Mobile already exists (Patient ID: {existing[0]}, Name: {existing[1]})"
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
    <h2>Search Patient by Mobile</h2>
    <form method="post">
        Mobile:
        <input type="text" name="search_mobile" required>
        <button type="submit">Search</button>
    </form>

    <p style="color:red;"><b>{error}</b></p>

    <hr>

    <h2>Add Patient</h2>

<a href="/export_patients">
    📤 <b>Export Patient List (Excel)</b>
</a>
<br><br>
    <form method="post">
        Date: <input type="date" name="appointment_date" required><br><br>
        Name: <input type="text" name="name" required><br><br>
        Type:
        <select name="patient_type">
            <option>New</option>
            <option>Old</option>
        </select><br><br>
        Mobile: <input type="text" name="mobile" required><br><br>
        City: <input type="text" name="city" required><br><br>
        Problem:<br>
        <textarea name="problem" required></textarea><br><br>
        <button type="submit">Save</button>
    </form>

    <hr>
    <h3>Patient List</h3>
    """

    for p in patients:
        html += f"""
        {p[0]} | {p[2]} | {p[4]}
        <a href="/patient/{p[0]}">View</a><br>
        """

    return html



# ---------------- PATIENT PAGE ----------------
@app.route("/patient/<int:patient_id>", methods=["GET", "POST"])
def patient(patient_id):
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

    plan = treatment[1] if treatment else ""
    final_amount = treatment[2] if treatment else 0
    consultant = treatment[3] if treatment else ""
    lab = treatment[4] if treatment else ""

    total_paid = sum(p[3] for p in payments) if payments else 0
    balance = final_amount - total_paid

    html = f"""
    <h2>Patient: {patient[2]}</h2>

    <h3>Treatment</h3>
    <form method="post">
        Plan:<br>
        <textarea name="plan">{plan}</textarea><br>
        Amount:<br>
        <input type="number" name="amount" value="{final_amount}"><br>
        Consultant:<br>
        <input name="consultant" value="{consultant}"><br>
        Lab:<br>
        <input name="lab" value="{lab}"><br><br>
        <button type="submit">Save Treatment</button>
    </form>

    <hr>
    <h3>Add Payment</h3>
    <form method="post">
        Date: <input type="date" name="payment_date" required>
        Amount: <input type="number" name="payment_amount" required>
        Mode:
        <select name="payment_mode">
            <option>Cash</option>
            <option>UPI</option>
            <option>Card</option>
        </select>
        <button type="submit">Add</button>
    </form>

    <h3>Payments</h3>
    """

    for p in payments:
        html += f"{p[2]} | {p[3]} | {p[4]}<br>"

    html += f"""
    <hr>
    <b>Total:</b> {final_amount}<br>
    <b>Paid:</b> {total_paid}<br>
    <b>Balance:</b> {balance}<br><br>

    <a href="/invoice/{patient_id}">🧾 Print / Download Invoice</a><br><br>
    <a href="/">⬅ Back</a>
    """

    return html


# ---------------- INVOICE PDF ----------------
@app.route("/invoice/<int:patient_id>")
def invoice(patient_id):
    db = get_db()

    patient = db.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
    treatment = db.execute("SELECT * FROM treatment WHERE patient_id=?", (patient_id,)).fetchone()
    payments = db.execute("SELECT * FROM payments WHERE patient_id=?", (patient_id,)).fetchall()

    total_paid = sum(p[3] for p in payments) if payments else 0
    final_amount = treatment[2]
    balance = final_amount - total_paid

    file_name = f"invoice_{patient_id}.pdf"
    pdf = canvas.Canvas(file_name, pagesize=(595, 842))

    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawCentredString(300, 810, "TREATMENT INVOICE")
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(300, 790, "Dr C Krishnarjuna Rao's Dental Clinic")

    pdf.drawString(40, 750, f"Patient Name: {patient[2]}")
    pdf.drawString(40, 735, f"Mobile: {patient[4]}")
    pdf.drawString(40, 720, f"City: {patient[5]}")

    pdf.drawString(40, 690, f"Treatment: {treatment[1]}")
    pdf.drawString(40, 675, f"Final Amount: {final_amount}")

    y = 640
    for p in payments:
        pdf.drawString(40, y, f"{p[2]}  {p[3]}  {p[4]}")
        y -= 15

    pdf.drawString(40, y - 10, f"Total Paid: {total_paid}")
    pdf.drawString(40, y - 25, f"Balance: {balance}")

    pdf.save()
    return send_file(file_name, as_attachment=True)

from openpyxl import Workbook
from datetime import datetime

from openpyxl import Workbook
from datetime import datetime

@app.route("/export_patients")
def export_patients():
    db = get_db()

    patients = db.execute("""
        SELECT id, appointment_date, name, mobile, city
        FROM patients
        ORDER BY appointment_date DESC
    """).fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Patients Report"

    headers = [
        "Appointment Date",
        "Patient Name",
        "Mobile",
        "City",
        "Final Amount",
        "Total Paid",
        "Balance"
    ]
    ws.append(headers)

    for p in patients:
        patient_id = p[0]

        # Get treatment amount
        treatment = db.execute(
            "SELECT final_amount FROM treatment WHERE patient_id=?",
            (patient_id,)
        ).fetchone()

        final_amount = treatment[0] if treatment else 0

        # Get total paid
        payments = db.execute(
            "SELECT SUM(amount) FROM payments WHERE patient_id=?",
            (patient_id,)
        ).fetchone()

        total_paid = payments[0] if payments[0] else 0

        balance = final_amount - total_paid

        ws.append([
            p[1],      # Date
            p[2],      # Name
            p[3],      # Mobile
            p[4],      # City
            final_amount,
            total_paid,
            balance
        ])

    today = datetime.now().strftime("%Y-%m-%d")
    file_name = f"patients_financial_report_{today}.xlsx"
    wb.save(file_name)

    return send_file(file_name, as_attachment=True)


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
