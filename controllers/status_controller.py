"""
BackTrack — StatusController (controllers/status_controller.py)
Owner: Chadrick Wallace (Status Tracking & Audit Log View — Feature #6)
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from models import db, LostReport, FoundItem, ClaimEnquiry, AuditLog
from controllers.verification_controller import (
    WorkflowError, admin_required, current_user, login_required, record_audit,
)

status_bp = Blueprint("status", __name__)

LOST_STATUSES = ["LOST", "MATCHED", "RETURNED"]
FOUND_STATUSES = ["FOUND", "MATCHED", "RETURNED"]
AUDIT_LOG_LIMIT = 100

def _find_record(itemId):
    """Looks up an active record by its code: LST-#### (lost report) or FND-#### (found item)."""
    code = (itemId or "").strip().upper()
    if code.startswith("LST-"):
        return "lost", LostReport.query.filter_by(reportId=code, isDeleted=False).first()
    if code.startswith("FND-"):
        return "found", FoundItem.query.filter_by(itemId=code, isDeleted=False).first()
    return None, None

def _can_view(user, kind, record):
    if user.isPoliceAdmin() or record.user_id == user.id:
        return True
    if kind == "found":
        return ClaimEnquiry.query.filter_by(found_item_id=record.id, user_id=user.id).first() is not None
    return False

def getItemStatus(itemId, user):
    kind, record = _find_record(itemId)
    if record is None or not _can_view(user, kind, record):
        return None

    if kind == "lost":
        code, zone_label, zone, steps = record.reportId, "Last seen", record.lastSeenZone, LOST_STATUSES
    else:
        code, zone_label, zone, steps = record.itemId, "Found at", record.foundZone, FOUND_STATUSES

    result = {
        "kind": kind,
        "code": code,
        "title": record.genericTitle,
        "category": record.category,
        "zone_label": zone_label,
        "zone": zone,
        "status": record.status,
        "steps": steps,
        "createdAt": record.createdAt,
        "history": None,
    }
    if user.isPoliceAdmin(): """The Audit Log view for Campus Police Admin"""
        result["history"] = (AuditLog.query.filter_by(targetRecordId=code)
                             .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).all())
    return result

def updateItemStatus(itemId, status, officer, note=""):
    if officer is None or not officer.isPoliceAdmin():
        raise WorkflowError("Only Campus Police can change an item's status.")

    kind, record = _find_record(itemId)
    if record is None:
        raise WorkflowError("No active record found with that ID.")

    code = record.reportId if kind == "lost" else record.itemId
    allowed = LOST_STATUSES if kind == "lost" else FOUND_STATUSES
    new_status = (status or "").strip().upper()
    if new_status not in allowed:
        raise WorkflowError(f"Choose one of: {', '.join(allowed)}.")

    old_status = record.status
    if new_status == old_status:
        raise WorkflowError(f"{code} is already {new_status}.")

    record.updateStatus(new_status)
    record_audit(officer, code, f"{old_status} -> {new_status}",
                 (note or "").strip() or "Status updated manually by officer.")
    db.session.commit()
    return record

@status_bp.route("/status")
@login_required
def track_status():
    """SDS Methods: getItemStatus(itemId), updateItemStatus(itemId, status)"""
    user = current_user()
    lookup = request.args.get("itemId", "").strip()

    result = None
    if lookup:
        result = getItemStatus(lookup, user)
        if result is None:
            flash("No item with that ID that you can view. Use an ID like FND-1001 or LST-2001.", "warning")

    context = {"lookup": lookup, "result": result, "is_admin": user.isPoliceAdmin(),
               "lost_statuses": LOST_STATUSES, "found_statuses": FOUND_STATUSES}

    if user.isPoliceAdmin():
        context.update(
            lost_reports=LostReport.query.filter_by(isDeleted=False).order_by(LostReport.id.desc()).all(),
            found_items=FoundItem.query.filter_by(isDeleted=False).order_by(FoundItem.id.desc()).all(),
            audit_logs=(AuditLog.query.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
                        .limit(AUDIT_LOG_LIMIT).all()),
        )
    else:
        context.update(
            lost_reports=(LostReport.query.filter_by(user_id=user.id, isDeleted=False)
                          .order_by(LostReport.id.desc()).all()),
            found_items=(FoundItem.query.filter_by(user_id=user.id, isDeleted=False)
                         .order_by(FoundItem.id.desc()).all()),
            claims=ClaimEnquiry.query.filter_by(user_id=user.id).order_by(ClaimEnquiry.id.desc()).all(),
        )
    return render_template("track_status.html", **context)

@status_bp.route("/status/update", methods=["POST"])
@admin_required
def update_status():
    item_id = request.form.get("itemId", "")
    try:
        record = updateItemStatus(item_id, request.form.get("status", ""), current_user(),
                                  request.form.get("note", ""))
    except WorkflowError as err:
        flash(str(err), "danger")
    else:
        flash(f"{item_id.strip().upper()} is now {record.status}.", "success")
    return redirect(url_for("status.track_status"))
