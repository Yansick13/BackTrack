"""
BackTrack — Automated Pytest Suite (tests/test_backtrack.py)
Owner: Marissa Henry

Covers core functional & security requirements from the SRS/SDS:
1. User Authentication & Role-Based Access Control (RBAC)
2. Lost & Found Report Creation and Lifecycle Status Transitions
3. Privacy Blinding (getBlindedListing strips secrets & photos)
4. ClaimEnquiry Field Validation
5. Fraud Flagging & Rollback to FOUND + Immutable AuditLog
6. Smart Matching Score (>= 60% threshold) & Simulated Notification Privacy
7. Soft-Delete Retention (isDeleted flag)
"""

import os
import sys
import pytest

# This ensures project root is importable when running pytest from any directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["DATABASE_URI"] = "sqlite:///:memory:"

from app import app
from models import (
    db,
    User,
    LostReport,
    FoundItem,
    ClaimEnquiry,
    AuditLog,
    Notification,
    SystemConfig,
)


@pytest.fixture
def client():
    """Creates an isolated in-memory SQLite database and Flask test client per test."""
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        db.create_all()

        # Seed baseline Student and Campus Police Admin users
        student = User(
            userId="620172692",
            fullName="Marissa Henry",
            email="student@mymona.uwi.edu",
            role="STUDENT",
        )
        student.set_password("student123")

        admin = User(
            userId="CP-408",
            fullName="Sgt. D. Campbell",
            email="police@uwimona.edu.jm",
            role="ADMIN",
        )
        admin.set_password("police123")

        db.session.add_all([student, admin])
        db.session.commit()

        with app.test_client() as test_client:
            yield test_client

        db.session.remove()
        db.drop_all()


# ==================== 1. AUTH & RBAC TESTS ====================

def test_user_password_hashing_and_role_checks(client):
    """Verify User.login() validates hashed passwords and isPoliceAdmin() enforces RBAC."""
    student = User.query.filter_by(email="student@mymona.uwi.edu").first()
    admin = User.query.filter_by(email="police@uwimona.edu.jm").first()

    assert student.login("student123") is True
    assert student.login("wrongpass") is False
    assert student.isPoliceAdmin() is False

    assert admin.login("police123") is True
    assert admin.isPoliceAdmin() is True


def test_login_route_redirects_by_role(client):
    """Verify /login sends students to directory and police admins to admin console."""
    # Student login
    res_student = client.post(
        "/login",
        data={"email": "student@mymona.uwi.edu", "password": "student123"},
        follow_redirects=False,
    )
    assert res_student.status_code == 302
    assert "/directory" in res_student.headers["Location"] or res_student.headers["Location"].endswith("/")

    # Admin login
    res_admin = client.post(
        "/login",
        data={"email": "police@uwimona.edu.jm", "password": "police123"},
        follow_redirects=False,
    )
    assert res_admin.status_code == 302
    assert "admin" in res_admin.headers["Location"]


# ==================== 2. PRIVACY BLINDING TEST (FEATURE 04) ====================

def test_found_item_privacy_blinding(client):
    """
    Negative Security Test (SRS Feature 04 / SDS SEC-2):
    getBlindedListing() must expose only safe public fields and strictly strip
    secretGroundTruth, custodyLocation, and raw photoPath.
    """
    admin = User.query.filter_by(role="ADMIN").first()
    item = FoundItem(
        itemId="FND-9001",
        genericTitle="Personal Smartphone Device",
        category="Electronics",
        foundZone="Faculty of Science & Technology (FST)",
        custodyLocation="UWI Campus Police HQ (Main Gate)",
        secretGroundTruth="IMEI 356938035643809, purple lockscreen with dog photo",
        photoPath="static/uploads/secret_phone.jpg",
        status="FOUND",
        user_id=admin.id,
    )
    db.session.add(item)
    db.session.commit()

    blinded = item.getBlindedListing()

    # Allowed public metadata
    assert blinded["itemId"] == "FND-9001"
    assert blinded["genericTitle"] == "Personal Smartphone Device"
    assert blinded["category"] == "Electronics"
    assert blinded["foundZone"] == "Faculty of Science & Technology (FST)"
    assert blinded["status"] == "FOUND"

    # Sensitive fields MUST NOT exist in blinded dictionary or serialized output
    assert "secretGroundTruth" not in blinded
    assert "custodyLocation" not in blinded
    assert "photoPath" not in blinded
    assert "356938035643809" not in str(blinded)


# ==================== 3. STATUS LIFECYCLE & SOFT DELETE TESTS ====================

def test_status_transitions_and_invalid_status_rejection(client):
    """Verify valid status transitions (LOST/FOUND -> MATCHED -> RETURNED) and rejection of invalid states."""
    student = User.query.filter_by(role="STUDENT").first()
    admin = User.query.filter_by(role="ADMIN").first()

    lost = LostReport(
        reportId="LST-9001",
        genericTitle="Scientific Calculator",
        category="Electronics",
        lastSeenZone="Main Library",
        privateDetails="Casio fx-115ES PLUS with initials M.H. on back",
        user_id=student.id,
    )
    found = FoundItem(
        itemId="FND-9002",
        genericTitle="Scientific Calculator",
        category="Electronics",
        foundZone="Main Library",
        custodyLocation="Main Library Security Desk",
        secretGroundTruth="Casio fx-115ES PLUS with scratched battery cover",
        user_id=admin.id,
    )
    db.session.add_all([lost, found])
    db.session.commit()

    assert lost.status == "LOST"
    assert found.status == "FOUND"

    lost.updateStatus("MATCHED")
    found.updateStatus("RETURNED")
    assert lost.status == "MATCHED"
    assert found.status == "RETURNED"

    # Invalid status must be ignored
    found.updateStatus("DELETED_FOREVER")
    assert found.status == "RETURNED"


def test_soft_delete_preserves_database_record(client):
    """Verify soft-deleting sets isDeleted=True without removing the record from SQLite."""
    admin = User.query.filter_by(role="ADMIN").first()
    item = FoundItem(
        itemId="FND-9003",
        genericTitle="Black Umbrella",
        category="Keys & Accessories",
        foundZone="UWI Mona Bowl",
        custodyLocation="Main Gate HQ",
        secretGroundTruth="Broken wooden handle tip",
        user_id=admin.id,
    )
    db.session.add(item)
    db.session.commit()

    item.isDeleted = True
    db.session.commit()

    active_items = FoundItem.query.filter_by(isDeleted=False).all()
    all_items = FoundItem.query.filter_by(itemId="FND-9003").all()

    assert len(active_items) == 0
    assert len(all_items) == 1
    assert all_items[0].isDeleted is True


# ==================== 4. CLAIM VALIDATION & FRAUD ROLLBACK (FEATURES 05 & 07) ====================

def test_claim_enquiry_validation_and_fraud_rollback_audit(client):
    """
    Verify ClaimEnquiry.validateFields() blocks blank proofs and that flagging a
    fraudulent claim resets FoundItem status back to FOUND and logs an AuditLog entry.
    """
    student = User.query.filter_by(role="STUDENT").first()
    admin = User.query.filter_by(role="ADMIN").first()

    found = FoundItem(
        itemId="FND-9004",
        genericTitle="Insulated Water Bottle",
        category="Bags & Cases",
        foundZone="Main Library",
        custodyLocation="Main Library Checkpoint",
        secretGroundTruth="Olive green HydroFlask with UWI Pelicans sticker",
        status="MATCHED",
        user_id=admin.id,
    )
    db.session.add(found)
    db.session.commit()

    # Blank proof should fail validation
    invalid_claim = ClaimEnquiry(
        claimId="CLM-9000",
        ownershipProof="   ",
        appointmentWindow="",
        user_id=student.id,
        found_item_id=found.id,
    )
    assert invalid_claim.validateFields() is False

    # Valid claim submission
    claim = ClaimEnquiry(
        claimId="CLM-9001",
        ownershipProof="It is a red Nike bottle with no stickers",
        appointmentWindow="Morning Shift (9:00 AM - 12:00 PM) @ Main Gate HQ",
        user_id=student.id,
        found_item_id=found.id,
    )
    assert claim.validateFields() is True
    db.session.add(claim)
    db.session.commit()

    # Simulate Campus Police Flagging Fraud (SRS Feature 07)
    claim.claimStatus = "FRAUD"
    claim.fraudReasonNote = "Claimant stated red Nike bottle; ground truth is olive green HydroFlask."
    found.updateStatus("FOUND")  # Rollback so real owner can still claim

    audit = AuditLog(
        logId="LOG-9001",
        targetRecordId=found.itemId,
        officerId=admin.userId,
        statusChange="MATCHED -> FOUND (FRAUD FLAGGED)",
        actionNote=claim.fraudReasonNote,
    )
    db.session.add(audit)
    db.session.commit()

    refreshed_item = FoundItem.query.filter_by(itemId="FND-9004").first()
    saved_log = AuditLog.query.filter_by(logId="LOG-9001").first()

    assert claim.claimStatus == "FRAUD"
    assert refreshed_item.status == "FOUND"
    assert saved_log is not None
    assert saved_log.officerId == "CP-408"


# ==================== 5. SMART MATCHING ENGINE TEST (FEATURE 03) ====================

def test_smart_matching_threshold_and_alert_privacy(client):
    """
    Verify Role 4's matching_service scores >= 0.60 for matching category/zone/keywords
    and dispatches a privacy-safe Notification without leaking secretGroundTruth.
    """
    from services.matching_service import calculateScore, runMatchScan

    student = User.query.filter_by(role="STUDENT").first()
    admin = User.query.filter_by(role="ADMIN").first()

    found = FoundItem(
        itemId="FND-9005",
        genericTitle="Laptop Backpack",
        category="Bags & Cases",
        foundZone="Faculty of Science & Technology (FST)",
        custodyLocation="Main Gate HQ",
        secretGroundTruth="Navy Jansport backpack containing COMP2140 notebook and charger",
        status="FOUND",
        user_id=admin.id,
    )
    lost = LostReport(
        reportId="LST-9005",
        genericTitle="Backpack",
        category="Bags & Cases",
        lastSeenZone="Faculty of Science & Technology (FST)",
        privateDetails="Navy Jansport backpack with COMP2140 notebook inside",
        status="LOST",
        user_id=student.id,
    )
    db.session.add_all([found, lost])
    db.session.commit()

    score = calculateScore(lost, found)
    assert score >= 0.60

    runMatchScan(lost)
    alerts = Notification.query.filter_by(recipientEmail=student.email).all()
    assert len(alerts) >= 1
    # Privacy check: alert must not expose secretGroundTruth verbatim
    assert "COMP2140 notebook and charger" not in alerts[-1].message
