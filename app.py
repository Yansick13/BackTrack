"""
BackTrack — Main Application Entry Point (app.py)
Owner: Role 1 (Tech Lead)

Initializes Flask, SQLite database, user sessions, and registers
all MVC controller blueprints matching Section 3.1 of the SDS.
"""

import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import db, User, Notification

# Import Controller Blueprints (Roles 2, 3, 4, 5)
from controllers.report_controller import report_bp
from controllers.directory_controller import directory_bp
from controllers.verification_controller import verification_bp
from controllers.status_controller import status_bp

app = Flask(__name__)

# Basic local configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SECRET_KEY"] = "backtrack-uwi-mona-comp2140-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'backtrack.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "static", "uploads")

# Ensure upload directory exists for Role 2 photo uploads
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Initialize database
db.init_app(app)

# Register MVC Blueprints
app.register_blueprint(report_bp)
app.register_blueprint(directory_bp)
app.register_blueprint(verification_bp)
app.register_blueprint(status_bp)


def get_current_user():
    """Helper to fetch the currently logged-in User object from the Flask session."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


@app.context_processor
def inject_user():
    """Makes `current_user` available automatically in every HTML template."""
    return {"current_user": get_current_user()}


# ==================== CORE AUTH & HOME ROUTES ====================

@app.route("/")
def home():
    """Redirects home traffic to the Public Blinded Directory."""
    return redirect(url_for("directory.view_directory"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Handles Student, Staff, and Campus Police authentication."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.login(password):
            session["user_id"] = user.id
            session["user_role"] = user.role
            flash(f"Welcome back, {user.fullName}!", "success")
            if user.isPoliceAdmin():
                return redirect(url_for("verification.admin_console"))
            return redirect(url_for("directory.view_directory"))
        else:
            flash("Invalid email or password. Please try again.", "danger")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Handles new Student account registration."""
    if request.method == "POST":
        # Grab the text typed into the HTML form
        user_id = request.form.get("userId", "").strip()
        full_name = request.form.get("fullName", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Basic validation: make sure nothing was left blank
        if not user_id or not full_name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        # Duplicate check (protects the unique=True columns in models.py)
        existing_user = User.query.filter(
            (User.email == email) | (User.userId == user_id)
        ).first()
        if existing_user:
            flash("An account with that Email or UWI ID already exists.", "danger")
            return redirect(url_for("register"))

        # Create the User object and hash the password
        new_user = User(
            userId=user_id,
            fullName=full_name,
            email=email,
            role="STUDENT"
        )
        new_user.set_password(password)

        # Save to SQLite
        db.session.add(new_user)
        db.session.commit()

        flash("Account created! You can now log in.", "success")
        return redirect(url_for("login"))

    # If the user just clicked the link (GET request), show the blank form
    return render_template("register.html")


@app.route("/logout")
def logout():
    """Clears the user session and returns to guest view."""
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("directory.view_directory"))


@app.route("/inbox")
def inbox():
    """Simulated Email Inbox (Displays alerts created by Role 4's NotificationService)."""
    notifications = Notification.query.order_by(Notification.createdAt.desc()).all()
    return render_template("inbox.html", notifications=notifications)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)