"""
BackTrack — VerificationController (controllers/verification_controller.py)
Owner: Role 5 (Claims, Police Console & Fraud Rollback — Feature #5)

TODO for Role 5:
1. Build templates/submit_claim.html and implement submitEnquiry().
2. Build templates/admin_console.html (restricted to current_user.isPoliceAdmin()).
3. Implement approveHandover() -> sets status RETURNED, writes AuditLog, triggers NotificationService.
4. Implement flagFraud() -> requires fraudReasonNote, resets FoundItem status to FOUND, writes AuditLog.
"""

from flask import Blueprint, render_template

verification_bp = Blueprint("verification", __name__)


@verification_bp.route("/claim/<int:item_id>", methods=["GET", "POST"])
def submit_claim(item_id):
    """SDS Method: submitEnquiry(user, itemId, proof, window) -> ClaimEnquiry"""
    return render_template("base.html")  # Replace with render_template("submit_claim.html")


@verification_bp.route("/admin/console")
def admin_console():
    """Campus Police Console for side-by-side verification, handover, and fraud flagging."""
    return render_template("base.html")  # Replace with render_template("admin_console.html")