"""
BackTrack — NotificationService (services/notification_service.py)
Owner: Davoy Gordon

1. Implement sendMatchAlert(email, message) -> saves to Notification table.
2. Implement sendStatusAlert(email, message) -> saves to Notification table.
3. PRIVACY RULE: Never include serial numbers, secretGroundTruth, or raw photos in alerts!
"""

from models import db, Notification


def sendMatchAlert(email: str, message: str) -> None:
    """Dispatches a privacy-safe match alert to the Simulated Email Inbox."""
    note = Notification(
        recipientEmail=email,
        subject="BackTrack Alert: Potential Match Found",
        message=message,
    )
    db.session.add(note)
    db.session.commit()


def sendStatusAlert(email: str, message: str) -> None:
    """Dispatches a status update alert to the Simulated Email Inbox."""
    note = Notification(
        recipientEmail=email,
        subject="BackTrack Update: Item Status Changed",
        message=message,
    )
    db.session.add(note)
    db.session.commit()