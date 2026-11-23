"""
BackTrack — StatusController (controllers/status_controller.py)
Owner: Role 5 (Status Tracking & Audit Log View — Feature #6)

TODO for Role 5:
1. Build templates/track_status.html showing item statuses (LOST, FOUND, MATCHED, RETURNED).
2. Implement getItemStatus(itemId) and updateItemStatus(itemId, status).
3. Display the read-only AuditLog table for Campus Police Admins.
"""

from flask import Blueprint, render_template

status_bp = Blueprint("status", __name__)


@status_bp.route("/status")
def track_status():
    """SDS Methods: getItemStatus(itemId), updateItemStatus(itemId, status)"""
    return render_template("base.html")  # Replace with render_template("track_status.html")