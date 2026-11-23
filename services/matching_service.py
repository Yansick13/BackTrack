"""
BackTrack — MatchingService (services/matching_service.py)
Owner: Role 4 (Smart Matching Engine — Feature #3)

TODO for Role 4:
1. Implement calculateScore(lost, found) -> float (0.0 to 1.0):
   - Same category: +0.40
   - Same campus zone: +0.30
   - Shared keywords (>3 chars) between privateDetails and secretGroundTruth: up to +0.30
2. Implement runMatchScan(report) -> list of matches >= matchThreshold (0.60).
3. Trigger NotificationService.sendMatchAlert() for each match >= 0.60.
"""

MATCH_THRESHOLD = 0.60


def calculateScore(lost_report, found_item) -> float:
    """Computes match confidence score between a LostReport and FoundItem."""
    return 0.0


def runMatchScan(report) -> list:
    """Scans opposite open reports and triggers alerts for scores >= 0.60."""
    return []