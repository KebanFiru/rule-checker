"""Content of the synthetic target SRS (single source for the PDF, the review DOCX and the DOCX variant)."""


def srs_blocks():
    """List of (type, text): both the PDF and the DOCX are generated from here. '@@' separates PDF text from DOCX text."""
    return [
     ("title", "Software Requirements Specification"),
     ("p", "Rev 2"),
     ("p", "Author: Ali Veli"),
     ("p", "Date: 2026-03-14"),
     ("p", "Table 1 Revision history"),
     ("table", [["Rev", "Description"], ["1", "First draft"], ["2", "Review fixes"]]),
     ("h", "1. Introduction"),
     ("p", "This document defines the requirements for userdata handling.@@This document defines the requirements for user data handling."),
     ("h", "2. Glossary"),
     ("p", "User: A person who signs in to the system."),
     ("h", "3. Requirements"),
     ("p", "FR-1 The system shall let the user sign in (UC-1.1)."),
     ("p", "FR-2 The system shall accept passwords of at least 6 characters (UC-1.2)."),
     ("p", "FR-3 The system shall close the session after 30 minutes of inactivity (UC-1.1)."),
     ("p", "FR-4 The system shall accept payments; for details see UC-9.9."),
     ("p", "FR-5 The system can provide reports."),
     ("p", "FR-6 The system shall send notifications in an appropriate format, if needed by e-mail etc. (UC-2.1); see FR-14."),
     ("p", "QR-A.1 Passwords shall be stored in plain text."),
     ("p", "QR-A.2 The system response time shall be at most 3 seconds."),
     ("p", "Table 2 Fees (for details see Table 5)"),
     ("table", [["Service", "Fee"], ["Standard", "250 USD"]]),
     ("h", "4. Use Cases"),
     ("p", "UC-1.1 Sign in"), ("p", "Priority: High"),
     ("p", "UC-1.2 Change password"), ("p", "Priority: Medium"),
     ("p", "UC-2.1 Send notification"), ("p", "Priority: Low"),
     ("p", "UC-2.2 Make payment"), ("p", "Priority: Urgent"),
     ("h", "5. Screen Designs"),
     ("img", "s1.png"), ("p", "Figure 1 UC-1.1 Sign-in screen"),
     ("img", "s2.png"), ("p", "Figure 2 UC-2.2 Payment screen (amount 100 €)"),
     ("img", "s3.png"),
     ("h", "6. Appendices"),
     ("p", "There are no appendices."),
    ]
