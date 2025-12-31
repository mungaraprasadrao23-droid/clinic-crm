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


def init_admin():
    db = get_db()
    db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)
    hashed = generate_password_hash("admin123")
    db.execute(
        "INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)",
        ("admin", hashed)
    )
    db.commit()


# ---------------- APP ----------------
app = Flask(__name__)
app.secret_key = "clinic-secret-key"

# ✅ auto-create admin safely
#init_admin()


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
    input, select, textarea, button {{
        width: 100%;
        padding: 14px;
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
    </style>
    </head>
    <body>
    <div class="container">
    <h2>Clinic CRM</h2>
    <a href="/logout">Logout</a>

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
        <div class="patient">
            <b>{p[2]}</b><br>
            {p[4]}<br>
            <a href="/patient/{p[0]}">View</a>
        </div>
        """

    html += """
    <a href="/export_patients">Export Excel</a>
    </div>
    </body>
    </html>
    """
    return html


# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
