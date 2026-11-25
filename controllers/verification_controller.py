"""
BackTrack — VerificationController (controllers/verification_controller.py)
Owner: Chadrick Wallace (Claims, Police Console & Fraud Rollback — Feature #5)
"""

from functools import wraps
from datetime import timezone, timedelta

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, session, url_for,
)

from models import db, User, FoundItem, ClaimEnquiry, AuditLog

try:  
    from services.notification_service import sendStatusAlert
except ImportError:  
    from notification_service import sendStatusAlert

verification_bp = Blueprint("verification", __name__)

# Ensures that Handovers only happen at Campus Police HQ 
HANDOVER_LOCATION = "Main Gate HQ"
HANDOVER_WINDOWS = [
    f"Morning Shift (9:00 AM - 12:00 PM) @ {HANDOVER_LOCATION}",
    f"Afternoon Shift (1:00 PM - 4:30 PM) @ {HANDOVER_LOCATION}",
]
MAX_PROOF_LENGTH = 2000

JAMAICA_TZ = timezone(timedelta(hours=-5), "JM")


class WorkflowError(ValueError):
    pass


def current_user():
    """Returns the logged-in User, or None for guests."""
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


def login_required(view):
    """Only signed-in students, staff or police may open the wrapped page."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    """Only Campus Police Admins may open the wrapped page."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user.isPoliceAdmin():
            flash("Campus Police access only.", "danger")
            return redirect(url_for("directory.view_directory"))
        return view(*args, **kwargs)
    return wrapper


def _next_id(column, prefix, start):
    """Builds the next sequential ID, e.g. CLM-3002, continuing from the highest stored."""
    highest = start - 1
    for (value,) in db.session.query(column).all():
        try:
            highest = max(highest, int(str(value).rsplit("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"{prefix}-{highest + 1}"


def next_claim_id():
    return _next_id(ClaimEnquiry.claimId, "CLM", 3001)


def next_log_id():
    return _next_id(AuditLog.logId, "LOG", 4001)


def record_audit(officer, target_id, status_change, note):   
    entry = AuditLog(
        logId=next_log_id(),
        targetRecordId=target_id,
        officerId=officer.userId,
        statusChange=status_change[:80],
        actionNote=note,
    )
    db.session.add(entry)
    return entry


def _photo_url(photo_path):    
    if not photo_path:
        return None
    path = photo_path.replace("\\", "/")
    if "static/" in path:
        path = path.split("static/", 1)[1]
    elif not path.startswith("uploads/"):
        path = "uploads/" + path.split("/")[-1]
    return url_for("static", filename=path)


@verification_bp.app_template_filter("jm_time")
def jm_time(value):
    """ Formats to jamaican time for templates"""
    if not value:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(JAMAICA_TZ).strftime("%b %d, %Y %I:%M %p")


def _claim_blocker(user, item):
    """Returns a message explaining why the user cannot claim the item, or None if they can."""
    if user.isPoliceAdmin():
        return "Campus Police accounts cannot file for ownership claims."
    if item.user_id == user.id:
        return "You have already logged this item as found. You are unable to claim it."
    if item.status == "RETURNED":
        return "This item has already been returned to its owner."
    earlier = (
        ClaimEnquiry.query
        .filter(ClaimEnquiry.user_id == user.id,
                ClaimEnquiry.found_item_id == item.id,
                ClaimEnquiry.claimStatus.in_(["PENDING", "FRAUD"]))
        .first()
    )
    if earlier and earlier.claimStatus == "PENDING":
        return "You already have a pending claim on this item. Please use our Tracking feature under Track Status."
    if earlier:
        return "Campus Police has rejected your earlier claim on this item. Please visit Main Gate HQ."
    return None


def submitEnquiry(user, itemId, proof, window):    
    item = db.session.get(FoundItem, itemId)
    if item is None or item.isDeleted:
        raise WorkflowError("That item is no longer listed.")

    blocker = _claim_blocker(user, item)
    if blocker:
        raise WorkflowError(blocker)

    proof = (proof or "").strip()
    window = (window or "").strip()
    if window not in HANDOVER_WINDOWS:
        raise WorkflowError("Choose one of the handover windows listed.")
    if len(proof) > MAX_PROOF_LENGTH:
        raise WorkflowError(f"Keep your proof under {MAX_PROOF_LENGTH} characters.")

    claim = ClaimEnquiry(
        claimId=next_claim_id(),
        ownershipProof=proof,
        appointmentWindow=window,
        claimStatus="PENDING",
        user_id=user.id,
        found_item_id=item.id,
    )
    if not claim.validateFields():
        raise WorkflowError("Describe how you can prove this item is yours.")

    db.session.add(claim)
    db.session.commit()
    return claim


def _load_pending_claim(claimId, officer):
    if officer is None or not officer.isPoliceAdmin():
        raise WorkflowError("Only Campus Police can review claims.")
    claim = db.session.get(ClaimEnquiry, claimId)
    if claim is None:
        raise WorkflowError("Claim not found.")
    if claim.claimStatus != "PENDING":
        raise WorkflowError(f"{claim.claimId} has already been reviewed.")
    return claim


def approveHandover(claimId, officer):
    """Approves a claim, sets the item to RETURNED, writes the AuditLog and alerts the claimant."""
    claim = _load_pending_claim(claimId, officer)
    item = claim.found_item
    if item.status == "RETURNED":
        raise WorkflowError(f"{item.itemId} has already been returned to another claimant.")

    previous = item.status
    claim.claimStatus = "APPROVED"
    item.updateStatus("RETURNED")
    record_audit(
        officer, item.itemId, f"{previous} -> RETURNED",
        f"Claim {claim.claimId} approved after verification. Handover window: {claim.appointmentWindow}.",
    )
    db.session.commit()

    sendStatusAlert(
        claim.claimant.email,
        f"Your ownership claim {claim.claimId} was approved. Bring your UWI ID to Campus Police HQ "
        f"(Main Gate) during your chosen window: {claim.appointmentWindow}.",
    )
    return claim


def flagFraud(claimId, officer, reason):
    """Rejects a claim as fraud. The item goes back to FOUND so the real owner can still claim it."""
    reason = (reason or "").strip()
    if not reason:
        raise WorkflowError("A fraud reason is required.")
    claim = _load_pending_claim(claimId, officer)
    item = claim.found_item

    claim.claimStatus = "FRAUD"
    claim.fraudReasonNote = reason

    previous = item.status
    if previous != "RETURNED": 
        item.updateStatus("FOUND")
    change = f"{previous} -> FOUND" if previous not in ("FOUND", "RETURNED") else f"{previous} (unchanged)"
    record_audit(
        officer, item.itemId, change,
        f"Claim {claim.claimId} flagged as fraud. Reason: {reason}",
    )
    db.session.commit()
    return claim


@verification_bp.route("/claim/<int:item_id>", methods=["GET", "POST"])
@login_required
def submit_claim(item_id):    
    user = current_user()
    item = db.session.get(FoundItem, item_id)
    if item is None or item.isDeleted:
        abort(404)

    blocker = _claim_blocker(user, item)
    if blocker:
        flash(blocker, "warning")
        return redirect(url_for("directory.view_directory"))

    proof, window = "", ""
    if request.method == "POST":
        proof = request.form.get("ownershipProof", "")
        window = request.form.get("appointmentWindow", "")
        try:
            claim = submitEnquiry(user, item.id, proof, window)
        except WorkflowError as err:
            flash(str(err), "danger")
        else:
            flash(f"Claim {claim.claimId} submitted. Track it here, and bring your UWI ID to {HANDOVER_LOCATION}.",
                  "success")
            return redirect(url_for("status.track_status"))
    
    return render_template("submit_claim.html", item=item.getBlindedListing(),
                           windows=HANDOVER_WINDOWS, proof=proof, window=window,
                           location=HANDOVER_LOCATION)


@verification_bp.route("/admin/console")
@admin_required
def admin_console():
    pending = (ClaimEnquiry.query.filter_by(claimStatus="PENDING")
               .order_by(ClaimEnquiry.createdAt).all())
    cases = [
        {"claim": c, "item": c.found_item, "claimant": c.claimant,
         "photo_url": _photo_url(c.found_item.photoPath)}
        for c in pending if not c.found_item.isDeleted
    ]
    reviewed = (ClaimEnquiry.query.filter(ClaimEnquiry.claimStatus != "PENDING")
                .order_by(ClaimEnquiry.createdAt.desc()).limit(15).all())
    return render_template("admin_console.html", cases=cases, reviewed=reviewed)


@verification_bp.route("/admin/claims/<int:claim_id>/approve", methods=["POST"])
@admin_required
def approve_handover(claim_id):
    try:
        claim = approveHandover(claim_id, current_user())
    except WorkflowError as err:
        flash(str(err), "danger")
    else:
        flash(f"Handover approved for {claim.claimId}. {claim.found_item.itemId} is now RETURNED.", "success")
    return redirect(url_for("verification.admin_console"))


@verification_bp.route("/admin/claims/<int:claim_id>/flag", methods=["POST"])
@admin_required
def flag_fraud(claim_id):
    try:
        claim = flagFraud(claim_id, current_user(), request.form.get("fraudReasonNote", ""))
    except WorkflowError as err:
        flash(str(err), "danger")
    else:
        flash(f"{claim.claimId} flagged as fraud. {claim.found_item.itemId} stays open for the real owner.",
              "warning")
    return redirect(url_for("verification.admin_console"))
