"""
BackTrack — Database Models (models.py)
Owner: Yanick Salmon

- User
- LostReport
- FoundItem
- ClaimEnquiry
- AuditLog
Plus helper tables:
- Notification (Simulated Email Inbox)
- SystemConfig (editable UWI Mona campus zones & item categories)
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    """Represents students, staff, and Campus Police administrators."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    userId = db.Column(db.String(20), unique=True, nullable=False)  # e.g., UWI ID or Badge #
    fullName = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="STUDENT")  # STUDENT, STAFF, ADMIN

    # Relationships (1 to 0..*)
    lost_reports = db.relationship("LostReport", backref="reporter", lazy=True)
    found_items = db.relationship("FoundItem", backref="finder", lazy=True)
    claims = db.relationship("ClaimEnquiry", backref="claimant", lazy=True)

    def set_password(self, raw_password: str) -> None:
        """Hashes and stores the user's password securely."""
        self.password_hash = generate_password_hash(raw_password)

    def login(self, password: str) -> bool:
        """Verifies user credentials against the stored password hash."""
        return check_password_hash(self.password_hash, password)

    def isPoliceAdmin(self) -> bool:
        """Returns True if the user holds Campus Police administrative privileges."""
        return self.role.upper() == "ADMIN"

    def __repr__(self) -> str:
        return f"<User {self.userId} ({self.role})>"


class LostReport(db.Model):
    """Represents a lost item report submitted by a student or staff member."""
    __tablename__ = "lost_reports"

    id = db.Column(db.Integer, primary_key=True)
    reportId = db.Column(db.String(20), unique=True, nullable=False)  # e.g., LST-1001
    genericTitle = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    lastSeenZone = db.Column(db.String(120), nullable=False)
    privateDetails = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="LOST")  # LOST, MATCHED, RETURNED
    isDeleted = db.Column(db.Boolean, nullable=False, default=False)
    createdAt = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Foreign Key
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    def updateStatus(self, newStatus: str) -> None:
        """Updates the lifecycle status of the lost report."""
        allowed = {"LOST", "MATCHED", "RETURNED"}
        if newStatus.upper() in allowed:
            self.status = newStatus.upper()

    def __repr__(self) -> str:
        return f"<LostReport {self.reportId} [{self.status}]>"


class FoundItem(db.Model):
    """Represents a found item logged in Campus Police custody."""
    __tablename__ = "found_items"

    id = db.Column(db.Integer, primary_key=True)
    itemId = db.Column(db.String(20), unique=True, nullable=False)  # e.g., FND-1001
    genericTitle = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    foundZone = db.Column(db.String(120), nullable=False)
    custodyLocation = db.Column(db.String(120), nullable=False)
    secretGroundTruth = db.Column(db.Text, nullable=False)  # Officer-only confidential details
    photoPath = db.Column(db.String(255), nullable=True)     # Officer-only uploaded image path
    status = db.Column(db.String(20), nullable=False, default="FOUND")  # FOUND, MATCHED, RETURNED
    isDeleted = db.Column(db.Boolean, nullable=False, default=False)
    createdAt = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Foreign Key & Relationships
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    claims = db.relationship("ClaimEnquiry", backref="found_item", lazy=True)

    def getBlindedListing(self) -> dict:
        """
        Privacy Blinding (SDS SEC-2):
        Returns ONLY safe public metadata. Strictly strips secretGroundTruth,
        custodyLocation, and raw photoPath so dishonest users cannot fabricate claims.
        """
        return {
            "id": self.id,
            "itemId": self.itemId,
            "genericTitle": self.genericTitle,
            "category": self.category,
            "foundZone": self.foundZone,
            "status": self.status,
            "createdAt": self.createdAt.strftime("%b %d, %Y") if self.createdAt else "",
        }

    def updateStatus(self, newStatus: str) -> None:
        """Updates the lifecycle status of the found item."""
        allowed = {"FOUND", "MATCHED", "RETURNED"}
        if newStatus.upper() in allowed:
            self.status = newStatus.upper()

    def __repr__(self) -> str:
        return f"<FoundItem {self.itemId} [{self.status}]>"


class ClaimEnquiry(db.Model):
    """Represents an ownership verification enquiry filed against a FoundItem."""
    __tablename__ = "claim_enquiries"

    id = db.Column(db.Integer, primary_key=True)
    claimId = db.Column(db.String(20), unique=True, nullable=False)  # e.g., CLM-1001
    ownershipProof = db.Column(db.Text, nullable=False)
    appointmentWindow = db.Column(db.String(120), nullable=False)
    claimStatus = db.Column(db.String(30), nullable=False, default="PENDING")  # PENDING, APPROVED, FRAUD
    fraudReasonNote = db.Column(db.Text, nullable=True)
    createdAt = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Foreign Keys
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    found_item_id = db.Column(db.Integer, db.ForeignKey("found_items.id"), nullable=False)

    def validateFields(self) -> bool:
        """Ensures required proof and handover appointment fields are present."""
        return bool(
            self.ownershipProof and self.ownershipProof.strip()
            and self.appointmentWindow and self.appointmentWindow.strip()
        )

    def __repr__(self) -> str:
        return f"<ClaimEnquiry {self.claimId} [{self.claimStatus}]>"


class AuditLog(db.Model):
    """Immutable log of all status updates, handover approvals, and fraud flags."""
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    logId = db.Column(db.String(25), unique=True, nullable=False)  # e.g., LOG-1001
    targetRecordId = db.Column(db.String(30), nullable=False)
    officerId = db.Column(db.String(30), nullable=False)
    statusChange = db.Column(db.String(80), nullable=False)
    actionNote = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<AuditLog {self.logId} on {self.targetRecordId}>"


class Notification(db.Model):
    """Stores simulated email alerts for reliable local demoing (no SMTP failures)."""
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    recipientEmail = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    createdAt = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<Notification to {self.recipientEmail}>"


class SystemConfig(db.Model):
    """Editable lookup table for UWI Mona campus zones and item categories (no migrations needed)."""
    __tablename__ = "system_config"

    id = db.Column(db.Integer, primary_key=True)
    configType = db.Column(db.String(30), nullable=False)  # "ZONE" or "CATEGORY"
    value = db.Column(db.String(120), nullable=False)

    def __repr__(self) -> str:
        return f"<SystemConfig {self.configType}: {self.value}>"