"""
BackTrack — ReportController (controllers/report_controller.py)
Owner: Role 2 (Lost & Found Reporting — Features #1 & #2)

TODO for Role 2:
1. Build templates/report_lost.html and implement submitLostReport().
2. Build templates/report_found.html (with optional photo upload) and implement submitFoundItem().
3. Call MatchingService.runMatchScan(new_report) after saving each report.
"""

from flask import Blueprint, render_template

report_bp = Blueprint("report", __name__)


@report_bp.route("/report/lost", methods=["GET", "POST"])
def report_lost():
    """SDS Method: submitLostReport(user, data) -> LostReport"""
    return render_template("base.html")  # Replace with render_template("report_lost.html")


@report_bp.route("/report/found", methods=["GET", "POST"])
def report_found():
    """SDS Method: submitFoundItem(user, data) -> FoundItem"""
    return render_template("base.html")  # Replace with render_template("report_found.html")