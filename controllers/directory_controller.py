"""
BackTrack — DirectoryController (controllers/directory_controller.py)
Owner: Role 3 (Blinded Directory, Search & Config — Feature #4)

TODO for Role 3:
1. Build templates/directory.html and implement searchDirectory(keyword, category, zone).
2. Always call item.getBlindedListing() so private details are NEVER sent to the template.
3. Build templates/manage_config.html so Police Admins can add/remove campusZones & categories.
"""

from flask import Blueprint, render_template
from models import FoundItem

directory_bp = Blueprint("directory", __name__)


@directory_bp.route("/directory")
def view_directory():
    """SDS Method: searchDirectory(keyword, category, zone) -> List<Map>"""
    # Starter query showing privacy blinding in action:
    items = FoundItem.query.filter_by(isDeleted=False).all()
    blinded_items = [item.getBlindedListing() for item in items]
    # Role 3: Create templates/directory.html and pass blinded_items, zones, categories
    return f"<h3>Blinded Directory Stub (Role 3)</h3><p>{len(blinded_items)} blinded items loaded. Replace with directory.html.</p><a href='/login'>Go to Login</a>"


@directory_bp.route("/admin/config", methods=["GET", "POST"])
def manage_config():
    """Admin-only route to manage campusZones and categories in SystemConfig."""
    return render_template("base.html")  # Replace with render_template("manage_config.html")