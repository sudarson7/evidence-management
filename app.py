import os
import random
import hashlib
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
)
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
import database

app = Flask(__name__)
app.config.from_object(Config)

mail = Mail(app)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Helper function to get database connection
def get_connection():
    return database.connect()

# Authentication Decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            if request.is_json or request.path.startswith('/api'):
                return jsonify({"success": False, "message": "Authentication required. Please login."}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# Send OTP via Email ONLY
def send_otp(email):
    otp = str(random.randint(100000, 999999))
    session["otp"] = otp
    session["otp_email"] = email

    msg = Message(
        subject=f"Evidence Verification System - Login OTP",
        sender=app.config.get("MAIL_DEFAULT_SENDER", app.config["MAIL_USERNAME"]),
        recipients=[email]
    )

    msg.body = f"""Hello,

Your 6-digit OTP for Evidence Verification System login is: {otp}

This OTP is valid for your current login session. Do not share this OTP with anyone.

Regards,
Blockchain Evidence Management Team
"""

    msg.html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="color: #06b6d4; margin: 0;">🛡️ EVIDENCE CHAIN</h2>
            <p style="color: #64748b; font-size: 13px; margin-top: 4px;">Blockchain Evidence Management System</p>
        </div>
        <div style="background-color: #f8fafc; border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 20px; border: 1px solid #cbd5e1;">
            <p style="color: #334155; font-size: 14px; margin-bottom: 10px;">Your 2FA Login Security Code:</p>
            <h1 style="color: #2563eb; font-size: 36px; letter-spacing: 8px; margin: 0; font-family: monospace;">{otp}</h1>
            <p style="color: #64748b; font-size: 12px; margin-top: 10px;">Valid for current login session. Do not share this code.</p>
        </div>
        <p style="color: #94a3b8; font-size: 12px; text-align: center;">If you did not request this code, please ignore this email.</p>
    </div>
    """

    try:
        mail.send(msg)
        print(f"[EMAIL DISPATCH] OTP email successfully sent via Gmail SMTP to {email}")
        return True, f"OTP sent to {email}. Check your Gmail inbox."
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send email to {email}: {e}")
        return False, f"Failed to deliver email: {str(e)}"


# Add entry to audit log blockchain
def add_audit_log(user, action, evidence_name=""):
    conn = get_connection()
    cursor = conn.cursor()

    timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    cursor.execute("""
        SELECT current_hash
        FROM audit_logs
        ORDER BY id DESC
        LIMIT 1
    """)

    last = cursor.fetchone()
    if last and last["current_hash"]:
        previous_hash = last["current_hash"]
    else:
        previous_hash = "0" * 64

    block_data = previous_hash + user + action + (evidence_name or "") + timestamp
    current_hash = hashlib.sha256(block_data.encode()).hexdigest()

    cursor.execute("""
        INSERT INTO audit_logs(
            user,
            action,
            evidence_name,
            timestamp,
            previous_hash,
            current_hash
        )
        VALUES(?,?,?,?,?,?)
    """, (user, action, evidence_name or "", timestamp, previous_hash, current_hash))

    conn.commit()
    conn.close()

# Initialize DB on start
database.initialize()

@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if "user" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    data = request.get_json() or {}
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    role = data.get("role", "").strip()

    if not email or not password or not role:
        return jsonify({"success": False, "message": "All fields are required."})

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email=? AND role=?", (email, role))
    user = cursor.fetchone()

    valid_user = False

    if user:
        stored_password = user["password"]
        # Check standard werkzeug hash OR fallback to plaintext for old records
        if stored_password.startswith("pbkdf2:") or stored_password.startswith("scrypt:"):
            if check_password_hash(stored_password, password):
                valid_user = True
        elif stored_password == password:
            valid_user = True
            # Seamlessly upgrade stored password to hash
            new_hash = generate_password_hash(password)
            cursor.execute("UPDATE users SET password=? WHERE id=?", (new_hash, user["id"]))
            conn.commit()

    conn.close()

    if valid_user:
        session["temp_user"] = email
        session["temp_role"] = role

        sent_ok, msg_status = send_otp(email)

        return jsonify({
            "success": sent_ok,
            "otp": sent_ok,
            "message": msg_status
        })

    return jsonify({
        "success": False,
        "message": "Invalid Email, Password, or Role selected."
    })


@app.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    
    if request.method == "GET":
        if "user" in session:
            return redirect(url_for("dashboard"))
        return render_template("otp.html")

    data = request.get_json() or {}
    entered_otp = str(data.get("otp", "")).strip()

    print("Entered OTP:", entered_otp)
    print("Session OTP:", session.get("otp"))

    if entered_otp and entered_otp == session.get("otp"):
        user_email = session.get("temp_user")
        user_role = session.get("temp_role")

        session["user"] = user_email
        session["role"] = user_role

        session.pop("otp", None)
        session.pop("temp_user", None)
        session.pop("temp_role", None)

        add_audit_log(user_email, "User Login Successful", "")

        return jsonify({
            "success": True,
            "message": "Authentication Verified! Redirecting..."
        })

    return jsonify({
        "success": False,
        "message": "Invalid OTP code. Please try again."
    })

@app.route("/resend_otp", methods=["POST"])
def resend_otp():
    email = session.get("otp_email")
    if not email:
        return jsonify({
            "success": False,
            "message": "Session expired. Please start login again."
        })

    otp = str(random.randint(100000, 999999))
    session["otp"] = otp
    print(f"[OTP RESEND] New OTP for {email}: {otp}")

    _, msg_status = send_otp(email)

    return jsonify({
        "success": True,
        "message": "New OTP dispatched successfully."
    })

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        if "user" in session:
            return redirect(url_for("dashboard"))
        return render_template("register.html")

    data = request.get_json() or {}
    fullname = data.get("fullname", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    role = data.get("role", "").strip()
    password = data.get("password", "").strip()

    if not all([fullname, email, phone, role, password]):
        return jsonify({"success": False, "message": "Please fill out all registration fields."})

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email=?", (email,))
    existing_user = cursor.fetchone()

    if existing_user:
        conn.close()
        return jsonify({"success": False, "message": "An account with this email already exists."})

    hashed_password = generate_password_hash(password)

    cursor.execute("""
        INSERT INTO users (fullname, email, phone, role, password)
        VALUES (?, ?, ?, ?, ?)
    """, (fullname, email, phone, role, hashed_password))

    conn.commit()
    conn.close()

    add_audit_log(email, "New Account Registered", f"Role: {role}")

    return jsonify({
        "success": True,
        "message": "Registration successful! You can now log in."
    })

@app.route("/logout")
def logout():
    user = session.get("user")
    if user:
        add_audit_log(user, "User Logout", "")
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM evidence")
    total_evidence = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM audit_logs")
    total_logs = cursor.fetchone()[0]

    cursor.execute("SELECT * FROM evidence ORDER BY id DESC")
    evidence = cursor.fetchall()

    verified = 0
    tampered = 0

    for item in evidence:
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], item["file_name"])
        if os.path.exists(filepath):
            sha = hashlib.sha256()
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    sha.update(chunk)
            if sha.hexdigest() == item["file_hash"]:
                verified += 1
            else:
                tampered += 1
        else:
            tampered += 1

    conn.close()

    return render_template(
        "dashboard.html",
        total_evidence=total_evidence,
        verified=verified,
        tampered=tampered,
        total_logs=total_logs
    )

@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "GET":
        return render_template("upload.html")

    caseid = request.form.get("caseid", "").strip()
    evidencename = request.form.get("evidencename", "").strip()

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file uploaded."})

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "message": "Please select a valid file."})

    filename = secure_filename(file.filename)
    # Avoid overwriting files with identical names by prefixing timestamp if file exists
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(filepath):
        time_stamp_prefix = datetime.now().strftime("%Y%m%d%H%M%S_")
        filename = secure_filename(time_stamp_prefix + file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    file.save(filepath)

    # SHA256 calculation
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                break
            sha.update(chunk)

    file_hash = sha.hexdigest()
    upload_date = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT current_hash
        FROM evidence
        ORDER BY id DESC
        LIMIT 1
    """)

    last = cursor.fetchone()
    if last and last["current_hash"]:
        previous_hash = last["current_hash"]
    else:
        previous_hash = "0" * 64

    block_data = previous_hash + file_hash + caseid + upload_date
    current_hash = hashlib.sha256(block_data.encode()).hexdigest()

    cursor.execute("""
        INSERT INTO evidence(
            case_id,
            evidence_name,
            file_name,
            file_hash,
            previous_hash,
            current_hash,
            uploaded_by,
            upload_date
        )
        VALUES(?,?,?,?,?,?,?,?)
    """, (
        caseid,
        evidencename,
        filename,
        file_hash,
        previous_hash,
        current_hash,
        session["user"],
        upload_date
    ))

    conn.commit()
    conn.close()

    add_audit_log(session["user"], "Uploaded Evidence", evidencename)

    return jsonify({
        "success": True,
        "message": "Evidence Uploaded & Blockchain Linked Successfully"
    })

@app.route("/evidence")
@login_required
def evidence():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM evidence
        ORDER BY id DESC
    """)
    records = cursor.fetchall()
    conn.close()

    evidence_list = []
    for item in records:
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], item["file_name"])
        if os.path.exists(filepath):
            sha = hashlib.sha256()
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    sha.update(chunk)
            file_status = (sha.hexdigest() == item["file_hash"])
        else:
            file_status = False

        evidence_list.append({
            "id": item["id"],
            "case_id": item["case_id"],
            "evidence_name": item["evidence_name"],
            "file_name": item["file_name"],
            "file_hash": item["file_hash"],
            "uploaded_by": item["uploaded_by"],
            "upload_date": item["upload_date"],
            "file_status": file_status
        })

    return render_template("evidence.html", evidence=evidence_list)

@app.route("/download/<int:evidence_id>")
@login_required
def download_evidence(evidence_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_name FROM evidence WHERE id=?", (evidence_id,))
    record = cursor.fetchone()
    conn.close()

    if not record:
        return "Evidence record not found", 404

    filename = record["file_name"]
    add_audit_log(session["user"], "Downloaded Evidence File", filename)
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)

@app.route("/verify")
@login_required
def verify():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM evidence
        ORDER BY id ASC
    """)
    blocks = cursor.fetchall()
    conn.close()

    blockchain = []
    previous_hash = "0" * 64

    for block in blocks:
        calculated_hash = hashlib.sha256(
            (
                block["previous_hash"]
                + block["file_hash"]
                + block["case_id"]
                + block["upload_date"]
            ).encode()
        ).hexdigest()

        chain_status = (
            block["previous_hash"] == previous_hash
            and block["current_hash"] == calculated_hash
        )

        filepath = os.path.join(app.config["UPLOAD_FOLDER"], block["file_name"])
        if os.path.exists(filepath):
            sha = hashlib.sha256()
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    sha.update(chunk)
            file_status = (sha.hexdigest() == block["file_hash"])
        else:
            file_status = False

        blockchain.append({
            "id": block["id"],
            "case_id": block["case_id"],
            "evidence_name": block["evidence_name"],
            "uploaded_by": block["uploaded_by"],
            "upload_date": block["upload_date"],
            "previous_hash": block["previous_hash"],
            "current_hash": block["current_hash"],
            "file_status": file_status,
            "chain_status": chain_status
        })

        previous_hash = block["current_hash"]

    total_blocks = len(blockchain)
    valid_blocks = sum(
        1 for block in blockchain
        if block["chain_status"] and block["file_status"]
    )
    tampered_blocks = total_blocks - valid_blocks
    overall_status = (tampered_blocks == 0)

    add_audit_log(session["user"], "Ran Blockchain Integrity Verification", f"Result: {'PASS' if overall_status else 'FAIL'}")

    return render_template(
        "verify.html",
        blockchain=blockchain,
        total_blocks=total_blocks,
        valid_blocks=valid_blocks,
        tampered_blocks=tampered_blocks,
        overall_status=overall_status
    )

@app.route("/audit")
@login_required
def audit():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM audit_logs
        ORDER BY id ASC
    """)
    logs = cursor.fetchall()
    conn.close()

    previous_hash = "0" * 64
    audit_valid = True

    for log in logs:
        calculated_hash = hashlib.sha256(
            (
                log["previous_hash"]
                + log["user"]
                + log["action"]
                + (log["evidence_name"] or "")
                + log["timestamp"]
            ).encode()
        ).hexdigest()

        if (
            log["previous_hash"] != previous_hash
            or log["current_hash"] != calculated_hash
        ):
            audit_valid = False
            break

        previous_hash = log["current_hash"]

    return render_template(
        "audit.html",
        logs=logs,
        audit_valid=audit_valid
    )

@app.route("/profile")
@login_required
def profile():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT fullname, email, phone, role
        FROM users
        WHERE email=?
        """,
        (session["user"],)
    )
    user = cursor.fetchone()
    conn.close()

    return render_template(
        "profile.html",
        user=user
    )

if __name__ == "__main__":
    app.run(debug=True)