from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import db, User, FoundItem, SystemConfig

directory_bp = Blueprint("directory", __name__)


def admin_required(view):
    """Only Campus Police Admins may open the wrapped page."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = User.query.get(session.get("user_id")) if session.get("user_id") else None
        if not user or not user.isPoliceAdmin():
            flash("Campus Police access only.", "danger")
            return redirect(url_for("directory.view_directory"))
        return view(*args, **kwargs)
    return wrapper


def config_values(config_type):
    return SystemConfig.query.filter_by(configType=config_type).order_by(SystemConfig.value).all()


def searchDirectory(keyword=None, category=None, zone=None):
    """Filter active FoundItem records (isDeleted == False), return BLINDED dicts only."""
    query = FoundItem.query.filter(FoundItem.isDeleted == False,   # noqa: E712
                                   FoundItem.status != "RETURNED")
    if keyword:
        query = query.filter(FoundItem.genericTitle.ilike(f"%{keyword}%"))
    if category:
        query = query.filter(FoundItem.category == category)
    if zone:
        query = query.filter(FoundItem.foundZone == zone)
    return [item.getBlindedListing() for item in query.order_by(FoundItem.id.desc()).all()]


@directory_bp.route("/directory")
def view_directory():
    keyword = request.args.get("keyword", "").strip()
    category = request.args.get("category", "")
    zone = request.args.get("zone", "")
    items = searchDirectory(keyword, category, zone)
    categories = [c.value for c in config_values("CATEGORY")]
    zones = [z.value for z in config_values("ZONE")]
    return render_template("directory.html", items=items, categories=categories, zones=zones,
                           keyword=keyword, sel_category=category, sel_zone=zone)


@directory_bp.route("/admin/config")
@admin_required
def manage_config():
    return render_template("manage_config.html",
                           categories=config_values("CATEGORY"), zones=config_values("ZONE"))


@directory_bp.route("/admin/config/add", methods=["POST"])
@admin_required
def add_config():
    config_type = request.form.get("kind", "").upper()
    value = request.form.get("value", "").strip()
    if config_type not in ("ZONE", "CATEGORY") or not value:
        flash("Please enter a value.", "warning")
    elif SystemConfig.query.filter(SystemConfig.configType == config_type,
                                   db.func.lower(SystemConfig.value) == value.lower()).first():
        flash(f"'{value}' already exists.", "warning")
    else:
        db.session.add(SystemConfig(configType=config_type, value=value))
        db.session.commit()
        flash(f"Added {config_type.lower()}: {value}", "success")
    return redirect(url_for("directory.manage_config"))


@directory_bp.route("/admin/config/remove/<int:config_id>", methods=["POST"])
@admin_required
def remove_config(config_id):
    entry = SystemConfig.query.get_or_404(config_id)
    db.session.delete(entry)
    db.session.commit()
    flash(f"Removed {entry.configType.lower()}: {entry.value}", "success")
    return redirect(url_for("directory.manage_config"))
