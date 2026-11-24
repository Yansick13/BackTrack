"""
BackTrack — MatchingService (services/matching_service.py)
Owner: Role 4 (Smart Matching Engine — Feature #3)

1. Implement calculateScore(lost, found) -> float (0.0 to 1.0):
   - Same category: +0.40
   - Same campus zone: +0.30
   - Shared keywords (>3 chars) between privateDetails and secretGroundTruth: up to +0.30
2. Implement runMatchScan(report) -> list of matches >= matchThreshold (0.60).
3. Trigger NotificationService.sendMatchAlert() for each match >= 0.60.
"""

from models import LostReport, FoundItem
from services.notification_service import sendMatchAlert

MATCH_THRESHOLD = 0.60

def isMatch(word, wordList):
    """Runs a word through a list of words to check if it matches"""
    for words in wordList:
        if word == words: 
            return True
    return False

def matchKeywords(keywords): # 'keywords' is a tuple containing two lists
    """Checks if two sentences have any matching words and returns how many of those words match"""
    lostWords, foundWords = keywords
    if len(lostWords) == 0:
        return 0

    if len(lostWords[0]) > 3 and isMatch(lostWords[0], foundWords):
        matches = 1
    else:
        matches = 0

    return matches + matchKeywords((lostWords[1:], foundWords))

def extractKeywords(lostReport, foundItem):
    """Extracts the words from the descriptions and returns them as lists"""
    punctuation = ".,?!'\";:()"
    lostWords = {words.strip(punctuation) for words in (lostReport.privateDetails or "").lower().split()}
    foundWords = {words.strip(punctuation) for words in (foundItem.secretGroundTruth or "").lower().split()}
    return list(lostWords), list(foundWords)

def calculateScore(lostReport, foundItem) -> float:
    """Computes match confidence score between a LostReport and FoundItem."""
    score = 0.00
    if lostReport.category == foundItem.category: score += 0.40
    if lostReport.lastSeenZone == foundItem.foundZone: score += 0.30
    matches = matchKeywords(extractKeywords(lostReport, foundItem))
    score += min(matches * 0.1, 0.3)
    return round(score, 2)

def message(lostReport, foundReport):
    return (
        f"Congratulations, we have found a possible match for {lostReport.genericTitle} "
        f"ID: {lostReport.reportId}\n\n"
        f"Found Item: {foundReport.genericTitle}\n" 
        f"ID: {foundReport.itemId}\n"
        f"Found at: {foundReport.foundZone}.\n\n"
        f"Please submit a claim to verify your ownership"
        )

def runMatchScan(report) -> list:
    """Scans opposite open reports and triggers alerts for scores >= 0.60."""
    matches = []
    isLost = isinstance(report, LostReport)
    if isLost:
        savedReports = FoundItem.query.filter_by(isDeleted=False, status="FOUND").all()
    else:
        savedReports = LostReport.query.filter_by(isDeleted=False, status="LOST").all()
    
    for s in savedReports:
        if isLost:
            lost = report
            found = s
        else:
            lost = s
            found = report
        
        score = calculateScore(lost, found)
        if score >= MATCH_THRESHOLD:
            matches.append((lost, found, score))
    
    sortedMatches = sorted(matches, key = lambda reports: reports[2], reverse = True)
    for match in sortedMatches:
        lostReport = match[0]
        foundReport = match[1]
        if lostReport.reporter:
           sendMatchAlert(lostReport.reporter.email, message(lostReport, foundReport))
    return sortedMatches
