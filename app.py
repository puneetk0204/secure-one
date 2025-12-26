from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_file,
)
from supabase_db import SupabaseDB, SupabaseFileManager
from gmail_otp import SecureOneOTP
import io
import os
from datetime import datetime
import requests

app = Flask(__name__)
app.secret_key = "secureone-secret-key-2024"
host = os.environ.get("APP_HOST", "127.0.0.1")

print("SecureOne Starting...")

# Initialize all systems
user_system = SupabaseDB()
file_system = SupabaseFileManager()
otp_service = SecureOneOTP()

print("All systems initialized!")


# Helper functionnn
def get_file_icon(filename):
    ext = os.path.splitext(filename)[1].lower()
    icons = {
        ".jpg": "image",
        ".jpeg": "image",
        ".png": "image",
        ".gif": "image",
        ".pdf": "pdf",
        ".doc": "doc",
        ".docx": "doc",
        ".txt": "doc",
        ".mp4": "video",
        ".avi": "video",
        ".mov": "video",
        ".mp3": "audio",
        ".wav": "audio",
        ".zip": "zip",
        ".rar": "zip",
    }
    return icons.get(ext, "doc")


app.jinja_env.globals.update(get_file_icon=get_file_icon)

# ROUTES


@app.route("/")  # home.html page
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])  # rsgister page ko connect
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form["name"]
    email = request.form["email"]
    confirm_email = request.form["confirm_email"]
    password = request.form["password"]
    confirm_password = request.form["confirm_password"]

    if email != confirm_email:
        flash("Emails do not match!", "error")
        return redirect(url_for("register"))

    if password != confirm_password:
        flash("Passwords do not match!", "error")
        return redirect(url_for("register"))

    if len(password) < 6:
        flash("Password must be at least 6 characters!", "error")
        return redirect(url_for("register"))

    success, message, existing_user = user_system.login(email, password)
    if existing_user:
        flash("User already exists! Please login.", "warning")
        return redirect(url_for("login"))

    result = otp_service.send_otp_email(email, name)

    if result["success"]:
        session["temp_user"] = {
            "name": name,
            "email": email,
            "password": password,
            "otp": result["otp"],
            "timestamp": datetime.now().timestamp(),
        }
        session["otp_email"] = email

        flash("OTP sent to your email! Please verify.", "success")
        return redirect(url_for("verify_otp_page"))
    else:
        flash(f'Failed to send OTP: {result.get("error", "Unknown error")}', "error")
        return redirect(url_for("register"))


@app.route("/verify_otp_page")  # otp verify pagee
def verify_otp_page():
    if "otp_email" not in session:
        flash("Please register first.", "warning")
        return redirect(url_for("register"))

    return render_template("verify_otp.html", email=session["otp_email"])


@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    if "otp_email" not in session or "temp_user" not in session:
        flash("Session expired. Please register again.", "error")
        return redirect(url_for("register"))

    user_email = request.form["email"]
    entered_otp = request.form["otp"]

    temp_user = session["temp_user"]
    current_time = datetime.now().timestamp()

    if current_time - temp_user["timestamp"] > 600:
        flash("OTP expired. Please request a new one.", "error")
        session.pop("temp_user", None)
        session.pop("otp_email", None)
        return redirect(url_for("register"))

    if entered_otp == temp_user["otp"]:
        name = temp_user["name"]
        email = temp_user["email"]
        password = temp_user["password"]

        success, message = user_system.register(name, email, password)

        if success:
            session["user_email"] = email
            session["user_name"] = name
            session["email_verified"] = True

            session.pop("temp_user", None)
            session.pop("otp_email", None)

            flash("Email verified! Registration successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash(f"Registration failed: {message}", "error")
            return redirect(url_for("register"))
    else:
        flash("Invalid OTP. Please try again.", "error")
        return redirect(url_for("verify_otp_page"))


@app.route("/resend_otp", methods=["POST"])  # res3nd otpp
def resend_otp():
    if "otp_email" not in session or "temp_user" not in session:
        flash("Session expired. Please register again.", "error")
        return redirect(url_for("register"))

    email = session["otp_email"]
    name = session["temp_user"]["name"]

    result = otp_service.send_otp_email(email, name)

    if result["success"]:
        session["temp_user"]["otp"] = result["otp"]
        session["temp_user"]["timestamp"] = datetime.now().timestamp()
        flash("New OTP sent to your email!", "success")
    else:
        flash("Failed to resend OTP. Please try again.", "error")

    return redirect(url_for("verify_otp_page"))


@app.route("/login", methods=["GET", "POST"])  # login page
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        success, message, user = user_system.login(email, password)

        if success:
            session["user_email"] = user["email"]
            session["user_name"] = user["name"]
            session["email_verified"] = True

            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash(message, "error")

    return render_template("login.html")


@app.route("/dashboard")  # dashboard
def dashboard():
    if "user_email" not in session:
        return redirect(url_for("login"))

    if not session.get("email_verified"):
        flash("Please verify your email to access dashboard.", "warning")
        return redirect(url_for("verify_otp_page"))

    success, files = file_system.get_user_files(session["user_email"])

    total_storage_mb = 0
    total_files = 0

    if success and files:
        total_files = len(files)
        total_storage_bytes = sum(file.get("file_size", 0) for file in files)
        total_storage_mb = round(total_storage_bytes / (1024 * 1024), 2)

    return render_template(
        "dashboard.html",
        user_name=session["user_name"],
        files=files if success else [],
        total_storage_mb=total_storage_mb,
        total_files=total_files,
    )


@app.route("/upload", methods=["POST"])  # uplaod file in drive
def upload_file():
    if "user_email" not in session:
        return redirect(url_for("login"))

    if "file" not in request.files:
        flash("No file selected", "error")
        return redirect(url_for("dashboard"))

    file = request.files["file"]
    if file.filename == "":
        flash("No file selected", "error")
        return redirect(url_for("dashboard"))

    success, message = file_system.upload_file(
        session["user_email"], file, file.filename
    )
    flash(message, "success" if success else "error")

    return redirect(url_for("dashboard"))


@app.route("/download/<file_id>")  # download file
def download_file(file_id):
    if "user_email" not in session:
        return redirect(url_for("login"))

    success, message, file_data, filename = file_system.download_file(
        session["user_email"], file_id
    )

    if success:
        return send_file(
            io.BytesIO(file_data), as_attachment=True, download_name=filename
        )
    else:
        flash(message, "error")
        return redirect(url_for("dashboard"))


@app.route("/delete_file/<file_id>", methods=["POST"])  # delete the file
def delete_file(file_id):
    if "user_email" not in session:
        return redirect(url_for("login"))

    try:
        # Get file details
        url = f"{file_system.url}/rest/v1/files?file_id=eq.{file_id}&user_email=eq.{session['user_email']}"
        response = requests.get(url, headers=file_system.headers)

        if response.status_code == 200 and response.json():
            file_data = response.json()[0]
            filename = file_data.get("original_name", "file")
            cloud_path = file_data.get("cloud_path", "")

            if cloud_path:
                # Delete from Supabase Storage
                from supabase_storage import SupabaseStorage

                storage = SupabaseStorage()
                storage.delete_file(cloud_path)

            # Delete from database
            delete_url = f"{file_system.url}/rest/v1/files?file_id=eq.{file_id}"
            delete_response = requests.delete(delete_url, headers=file_system.headers)

            if delete_response.status_code == 204:
                flash(f'File "{filename}" deleted successfully!', "success")
            else:
                flash("File could not be deleted from database", "error")
        else:
            flash("File not found", "error")

    except Exception as e:
        flash(f"Delete failed: {str(e)}", "error")

    return redirect(url_for("dashboard"))


@app.route("/profile")  # our profile page
def profile():
    if "user_email" not in session:
        return redirect(url_for("login"))

    return render_template(
        "profile.html", user_name=session["user_name"], user_email=session["user_email"]
    )


@app.route("/logout")  # logout
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for("home"))


if __name__ == "__main__":
    print("\nSecureOne running on: http://localhost:5000")
    print("Starting server...")
    print(f"Host: {host}")
    app.run(debug=True, port=5000, host=host)
