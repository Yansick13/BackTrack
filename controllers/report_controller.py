"""Lost and found reporting routes (Role 2)."""

import os
import secrets
from datetime import date

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from models import AuditLog, FoundItem, LostReport, SystemConfig, User, db
from services.matching_service import runMatchScan

report_bp = Blueprint("report", __name__)
bp = report_bp

ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}


def _config_values(config_type: str) -> list[str]:
    rows = (
        SystemConfig.query.filter_by(configType=config_type)
        .order_by(SystemConfig.value)
        .all()
    )
    return [row.value for row in rows]


def _generate_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(3).upper()}"


def _current_user_id() -> int | None:
    user_id = session.get("user_id")
    return int(user_id) if user_id is not None else None


def _validate_text(name: str, value: str, max_length: int) -> str | None:
    value = value.strip()
    if not value:
        return f"{name} is required."
    if len(value) > max_length:
        return f"{name} must be {max_length} characters or fewer."
    return None


def _validate_submission(
    record_type: str, categories: list[str], zones: list[str]
) -> tuple[dict | None, list[str]]:
    form = request.form
    title = form.get("title", "").strip()
    category = form.get("category", "").strip()
    zone = form.get("zone", "").strip()
    custody_location = form.get("custody_location", "").strip()
    secret_details = form.get("secret_details", "").strip()
    serial_number = form.get("serial_number", "").strip()
    event_date_text = form.get("event_date", "").strip()

    checks = [
        _validate_text("Title", title, 120),
        _validate_text("Category", category, 80),
        _validate_text("Location / zone", zone, 120),
        _validate_text("Secret details", secret_details, 2000),
        (
            "Serial number must be 150 characters or fewer."
            if len(serial_number) > 150
            else None
        ),
    ]
    if record_type == "found":
        checks.append(_validate_text("Custody location", custody_location, 120))

    errors = [message for message in checks if message]

    try:
        event_date = date.fromisoformat(event_date_text)
    except ValueError:
        event_date = None

    if not event_date_text:
        errors.append("Date is required.")
    elif event_date is None:
        errors.append("Enter a valid date.")
    elif event_date > date.today():
        errors.append("The date cannot be in the future.")

    if category and category not in categories:
        errors.append("Select a valid category.")
    if zone and zone not in zones:
        errors.append("Select a valid location / zone.")

    if record_type == "found":
        photo = request.files.get("photo")
        if photo and photo.filename and not _photo_extension(photo.filename):
            errors.append("Photo must be a JPG, PNG, WebP, or GIF file.")

    if errors:
        return None, errors

    return {
        "title": title,
        "category": category,
        "zone": zone,
        "custody_location": custody_location,
        "secret_details": secret_details,
        "serial_number": serial_number or None,
        "event_date": event_date,
    }, []


def _photo_extension(filename: str) -> str | None:
    safe_name = secure_filename(filename)
    if "." not in safe_name:
        return None
    extension = safe_name.rsplit(".", 1)[-1].lower()
    return extension if extension in ALLOWED_PHOTO_EXTENSIONS else None


def _upload_folder() -> str:
    return current_app.config.get(
        "UPLOAD_FOLDER", os.path.join(current_app.root_path, "static", "uploads")
    )


def _save_photo(photo: FileStorage | None) -> str | None:
    if photo is None or not photo.filename:
        return None

    extension = _photo_extension(photo.filename)
    if extension is None:
        raise ValueError("Invalid photo type.")

    upload_folder = _upload_folder()
    os.makedirs(upload_folder, exist_ok=True)
    filename = f"{secrets.token_hex(16)}.{extension}"
    photo.save(os.path.join(upload_folder, filename))
    return f"static/uploads/{filename}"


def _format_private_details(data: dict) -> str:
    parts = [data["secret_details"], f"Date: {data['event_date'].isoformat()}"]
    if data["serial_number"]:
        parts.append(f"Serial: {data['serial_number']}")
    return " | ".join(parts)


def _add_audit_log(user_id: int, record_id: str, action: str) -> None:
    user = db.session.get(User, user_id)
    if user is None:
        raise LookupError("The reporting user no longer exists.")
    db.session.add(
        AuditLog(
            logId=_generate_id("LOG"),
            targetRecordId=record_id,
            officerId=user.userId,
            statusChange=action,
            actionNote=f"{action.replace('_', ' ').title()} submitted by {user.fullName}.",
        )
    )


def _submit_report(record_type: str, user_id: int, data: dict) -> bool:
    photo_path = _save_photo(request.files.get("photo")) if record_type == "found" else None
    details = _format_private_details(data)

    if record_type == "lost":
        record = LostReport(
            reportId=_generate_id("LST"),
            genericTitle=data["title"],
            category=data["category"],
            lastSeenZone=data["zone"],
            privateDetails=details,
            status="LOST",
            user_id=user_id,
        )
        record_id = record.reportId
        success_message = f"Your lost item report ({record_id}) was submitted successfully."
        action = "LOST_REPORT_CREATED"
    else:
        record = FoundItem(
            itemId=_generate_id("FND"),
            genericTitle=data["title"],
            category=data["category"],
            foundZone=data["zone"],
            custodyLocation=data["custody_location"],
            secretGroundTruth=details,
            photoPath=photo_path,
            status="FOUND",
            user_id=user_id,
        )
        record_id = record.itemId
        success_message = f"Your found item report ({record_id}) was submitted successfully."
        action = "FOUND_ITEM_CREATED"

    try:
        db.session.add(record)
        _add_audit_log(user_id, record_id, action)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        if photo_path:
            photo_file = os.path.join(_upload_folder(), os.path.basename(photo_path))
            if os.path.exists(photo_file):
                os.remove(photo_file)
        current_app.logger.exception("Could not save %s report", record_type)
        flash("The report could not be saved. Please try again.", "danger")
        return False

    try:
        runMatchScan(record)
    except Exception:
        current_app.logger.exception("Match scan failed for %s", record_id)

    flash(success_message, "success")
    return True


@report_bp.route("/report/lost", methods=["GET", "POST"])
def report_lost():
    user_id = _current_user_id()
    if user_id is None:
        flash("Please log in to submit a lost report.", "warning")
        return redirect(url_for("login"))

    categories = _config_values("CATEGORY")
    zones = _config_values("ZONE")

    if request.method == "POST":
        data, errors = _validate_submission("lost", categories, zones)
        if errors:
            for error in errors:
                flash(error, "danger")
        elif data is not None and _submit_report("lost", user_id, data):
            return redirect(url_for("report.report_lost"))

    return render_template(
        "report_lost.html",
        categories=categories,
        zones=zones,
        form=request.form,
    )


@report_bp.route("/report/found", methods=["GET", "POST"])
def report_found():
    user_id = _current_user_id()
    if user_id is None:
        flash("Please log in to report a found item.", "warning")
        return redirect(url_for("login"))

    categories = _config_values("CATEGORY")
    zones = _config_values("ZONE")

    if request.method == "POST":
        data, errors = _validate_submission("found", categories, zones)
        if errors:
            for error in errors:
                flash(error, "danger")
        elif data is not None and _submit_report("found", user_id, data):
            return redirect(url_for("report.report_found"))

    return render_template(
        "report_found.html",
        categories=categories,
        zones=zones,
        form=request.form,
    )


def register_routes(app) -> None:
    app.register_blueprint(report_bp)
