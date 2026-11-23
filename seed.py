"""
BackTrack — Database Seed Script (seed.py)
Owner: Role 1 (Tech Lead)

Run this once to initialize backtrack.db with demo accounts, UWI Mona
zones/categories, and realistic sample records for development and demos.

Usage:
    python seed.py
"""

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


def seed_database():
    with app.app_context():
        # Reset tables cleanly for predictable local testing
        db.drop_all()
        db.create_all()

        # 1. Seed Demo Accounts
        student = User(
            userId="620147578",
            fullName="Yanick Salmon",
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

        # 2. Seed Editable UWI Mona Campus Zones & Item Categories
        default_zones = [
            "Faculty of Science & Technology (FST)",
            "Main Library",
            "Faculty of Social Sciences (FSS)",
            "Students' Union / Undercroft",
            "Halls of Residence (Taylor / Irvine / Rex)",
            "UWI Mona Bowl",
        ]
        default_categories = [
            "Electronics",
            "ID & Cards",
            "Bags & Cases",
            "Keys & Accessories",
            "Books & Documents",
        ]

        for zone in default_zones:
            db.session.add(SystemConfig(configType="ZONE", value=zone))
        for category in default_categories:
            db.session.add(SystemConfig(configType="CATEGORY", value=category))

        # 3. Seed Sample Found Items (Custody Registry)
        f1 = FoundItem(
            itemId="FND-1001",
            genericTitle="Personal Smartphone Device",
            category="Electronics",
            foundZone="Faculty of Science & Technology (FST)",
            custodyLocation="UWI Campus Police HQ (Main Gate)",
            secretGroundTruth="Black Samsung Galaxy S23 Ultra in matte Spigen case, Negril sunset wallpaper, small crack bottom-left.",
            status="FOUND",
            user_id=admin.id,
        )
        f2 = FoundItem(
            itemId="FND-1002",
            genericTitle="Insulated Water Bottle",
            category="Bags & Cases",
            foundZone="Main Library",
            custodyLocation="Main Library Security Checkpoint",
            secretGroundTruth="32oz Olive Green HydroFlask with UWI Pelicans sticker and dent on base rim.",
            status="FOUND",
            user_id=admin.id,
        )
        f3 = FoundItem(
            itemId="FND-1003",
            genericTitle="Set of Vehicle & Room Keys",
            category="Keys & Accessories",
            foundZone="Students' Union / Undercroft",
            custodyLocation="UWI Campus Police HQ (Main Gate)",
            secretGroundTruth="Kia flip key fob on black braided leather lanyard with two brass padlock keys.",
            status="MATCHED",
            user_id=admin.id,
        )
        f4 = FoundItem(
            itemId="FND-1004",
            genericTitle="University Identification Card",
            category="ID & Cards",
            foundZone="Faculty of Social Sciences (FSS)",
            custodyLocation="UWI Campus Police HQ (Main Gate)",
            secretGroundTruth="UWI Smart ID in clear holder with blue lanyard, belongs to FSS undergraduate.",
            status="RETURNED",
            user_id=admin.id,
        )

        db.session.add_all([f1, f2, f3, f4])
        db.session.commit()

        # 4. Seed Sample Lost Report (Matches FND-1001 for quick testing!)
        l1 = LostReport(
            reportId="LST-2001",
            genericTitle="Smartphone Device",
            category="Electronics",
            lastSeenZone="Faculty of Science & Technology (FST)",
            privateDetails="Black Samsung Galaxy S23 Ultra in matte Spigen case with sunset wallpaper.",
            status="LOST",
            user_id=student.id,
        )
        db.session.add(l1)

        # 5. Seed Sample Claim Enquiry
        c1 = ClaimEnquiry(
            claimId="CLM-3001",
            ownershipProof="Kia key fob attached to a black braided leather lanyard with two brass locker keys.",
            appointmentWindow="Afternoon Shift (1:00 PM - 4:30 PM) @ Main Gate HQ",
            claimStatus="PENDING",
            user_id=student.id,
            found_item_id=f3.id,
        )
        db.session.add(c1)

        # 6. Seed Initial Audit Log Entry
        a1 = AuditLog(
            logId="LOG-4001",
            targetRecordId="FND-1004",
            officerId=admin.userId,
            statusChange="FOUND -> RETURNED",
            actionNote="Verified student UWI ID at Main Gate HQ and completed handover.",
        )
        db.session.add(a1)

        # 7. Seed Sample Simulated Email Notification
        n1 = Notification(
            recipientEmail=student.email,
            subject="BackTrack Alert: Welcome to UWI Mona Lost & Found",
            message="Your account is active. You will receive privacy-safe alerts here whenever a potential match (>=60%) or status update occurs.",
        )
        db.session.add(n1)

        db.session.commit()
        print("Database seeded successfully!")
        print("Demo Student Login: student@mymona.uwi.edu / student123")
        print("Demo Police Login:  police@uwimona.edu.jm  / police123")


if __name__ == "__main__":
    seed_database()