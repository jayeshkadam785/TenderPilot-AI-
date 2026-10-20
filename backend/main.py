import os
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# =========================================================
# 1. FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="TenderPilot AI API",
    description=(
        "Tender analysis API for MSMEs. "
        "Extracts preliminary tender requirements from supplied text."
    ),
    version="1.0.0",
)


# =========================================================
# 2. CORS CONFIGURATION
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# =========================================================
# 3. REQUEST MODELS
# =========================================================

class AnalyzeRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=200000,
        description="Tender notice text to analyze",
    )


# =========================================================
# 4. DEMO TENDER DATA
# =========================================================

DEMO_TENDERS = [
    {
        "id": "TP-DEMO-001",
        "title": "Supply of Computer Equipment",
        "department": "Demo Government Department",
        "location": "Maharashtra",
        "estimated_value": 500000,
        "emd": 10000,
        "deadline": "2026-12-15",
        "category": "IT Equipment",
        "status": "Demo",
        "source": "Synthetic demonstration data",
        "verified": False,
    },
    {
        "id": "TP-DEMO-002",
        "title": "Office Stationery Supply",
        "department": "Demo Municipal Department",
        "location": "Maharashtra",
        "estimated_value": 200000,
        "emd": 5000,
        "deadline": "2026-12-20",
        "category": "Stationery",
        "status": "Demo",
        "source": "Synthetic demonstration data",
        "verified": False,
    },
    {
        "id": "TP-DEMO-003",
        "title": "Website Development Services",
        "department": "Demo Public Department",
        "location": "India",
        "estimated_value": 800000,
        "emd": 15000,
        "deadline": "2026-12-25",
        "category": "IT Services",
        "status": "Demo",
        "source": "Synthetic demonstration data",
        "verified": False,
    },
]


# =========================================================
# 5. HELPER FUNCTIONS
# =========================================================

NOT_FOUND = "Not stated in supplied text"


def clean(value: Any) -> str:
    """Clean extra spaces and punctuation from extracted text."""

    value = str(value)
    value = re.sub(r"[ \t]+", " ", value)
    return value.strip(" \t\r\n:;,-")


def unique(items: list[str]) -> list[str]:
    """Remove duplicate strings while preserving their order."""

    result = []
    seen = set()

    for item in items:
        item = clean(item)

        if item and item.lower() not in seen:
            result.append(item)
            seen.add(item.lower())

    return result


# =========================================================
# 6. TENDER TEXT ANALYSIS
# =========================================================

def extract_findings(text: str) -> dict:
    """
    Extract preliminary tender information using rule-based matching.

    This function does not verify the information against an
    official tender portal. All findings must be checked manually.
    """

    if not isinstance(text, str):
        text = ""

    text = text.strip()
    lines = text.splitlines()

    if not text:
        return {
            "possible_deadline": NOT_FOUND,
            "possible_emd": NOT_FOUND,
            "turnover": NOT_FOUND,
            "experience": NOT_FOUND,
            "documents": [],
            "corrigendum": NOT_FOUND,
        }

    # -----------------------------------------------------
    # A. DEADLINE EXTRACTION
    # -----------------------------------------------------

    date_pattern = (
        r"\b(?:"
        r"\d{1,2}\s+"
        r"(?:January|February|March|April|May|June|July|"
        r"August|September|October|November|December)"
        r"\s+\d{4}"
        r"|"
        r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
        r"|"
        r"\d{4}-\d{2}-\d{2}"
        r")\b"
    )

    time_pattern = (
        r"\b\d{1,2}:\d{2}\s*(?:AM|PM)?"
        r"(?:\s*(?:IST|UTC))?\b"
        r"|\b\d{1,2}\s*(?:AM|PM)"
        r"(?:\s*(?:IST|UTC))?\b"
    )

    deadline = None

    deadline_label = re.compile(
        r"(?i)\b(?:"
        r"bid\s+submission\s+deadline"
        r"|submission\s+deadline"
        r"|deadline"
        r"|closing\s+date"
        r"|last\s+date"
        r"|due\s+date"
        r"|bid\s+end\s+date"
        r")\s*[:=\-]?\s*(.*)"
    )

    for line in lines:
        match = deadline_label.search(line)

        if not match:
            continue

        value = clean(match.group(1))
        date_match = re.search(date_pattern, value, re.I)

        if date_match:
            candidate = date_match.group(0)
            remainder = value[date_match.end():]

            time_match = re.search(
                time_pattern,
                remainder,
                re.I,
            )

            if time_match:
                candidate += ", " + clean(time_match.group(0))

            deadline = candidate
            break

    # Fallback: use the first date found in the supplied text.
    if not deadline:
        date_match = re.search(date_pattern, text, re.I)

        if date_match:
            candidate = date_match.group(0)
            remainder = text[date_match.end():date_match.end() + 60]

            time_match = re.search(
                time_pattern,
                remainder,
                re.I,
            )

            if time_match:
                candidate += ", " + clean(time_match.group(0))

            deadline = candidate

    if not deadline:
        deadline = NOT_FOUND

    # -----------------------------------------------------
    # B. EMD / BID SECURITY
    # -----------------------------------------------------

    emd = None

    emd_label = re.compile(
        r"(?i)\b(?:"
        r"EMD"
        r"|earnest\s+money\s+deposit"
        r"|bid\s+security"
        r"|earnest\s+money"
        r")\b"
    )

    amount_pattern = re.compile(
        r"(?i)(?:"
        r"₹\s*|Rs\.?\s*|INR\s*"
        r")?"
        r"\d[\d,]*(?:\.\d+)?"
        r"(?:\s*(?:crores?|lakhs?|millions?|thousands?))?"
    )

    for line in lines:
        label_match = emd_label.search(line)

        if not label_match:
            continue

        # Look for an amount after the EMD label first.
        remainder = line[label_match.end():]
        amount_match = amount_pattern.search(remainder)

        if amount_match and re.search(r"\d", amount_match.group(0)):
            emd = clean(amount_match.group(0))
            break

        # If the label is at the end, check the full line.
        amount_matches = list(amount_pattern.finditer(line))

        for match in amount_matches:
            candidate = clean(match.group(0))

            if re.search(r"\d", candidate):
                emd = candidate
                break

        if emd:
            break

    if not emd:
        if emd_label.search(text):
            emd = "Mentioned; amount not extracted"
        else:
            emd = NOT_FOUND

    # -----------------------------------------------------
    # C. TURNOVER REQUIREMENT
    # -----------------------------------------------------

    turnover_lines = []

    for index, line in enumerate(lines):
        if re.search(r"(?i)\bturnover\b", line):
            turnover_lines.append(clean(line))

        elif re.search(r"(?i)\bturnover\s+requirement\b", line):
            turnover_lines.append(clean(line))

            for following in lines[index + 1:index + 4]:
                following = clean(following)

                if not following:
                    continue

                if re.search(
                    r"(?i)^(experience|required documents|"
                    r"corrigendum|deadline)\s*:?",
                    following,
                ):
                    break

                turnover_lines.append(following)

    turnover_lines = unique(turnover_lines)

    turnover = (
        " | ".join(turnover_lines)[:500]
        if turnover_lines
        else NOT_FOUND
    )

    # -----------------------------------------------------
    # D. EXPERIENCE REQUIREMENT
    # -----------------------------------------------------

    experience_lines = []

    for index, line in enumerate(lines):
        if re.search(r"(?i)\bexperience\b", line):
            experience_lines.append(clean(line))

        if re.search(r"(?i)\bexperience\s+requirement\b", line):
            for following in lines[index + 1:index + 4]:
                following = clean(following)

                if not following:
                    continue

                if re.search(
                    r"(?i)^(required documents|documents|"
                    r"corrigendum|deadline|turnover)\s*:?",
                    following,
                ):
                    break

                experience_lines.append(following)

    experience_lines = unique(experience_lines)

    experience = (
        " | ".join(experience_lines)[:500]
        if experience_lines
        else NOT_FOUND
    )

    # -----------------------------------------------------
    # E. REQUIRED DOCUMENTS
    # -----------------------------------------------------

    documents = []

    document_heading = re.compile(
        r"(?i)^\s*(?:"
        r"required\s+documents"
        r"|documents\s+required"
        r"|list\s+of\s+documents"
        r"|document\s+checklist"
        r"|supporting\s+documents"
        r")\s*:?\s*$"
    )

    stop_heading = re.compile(
        r"(?i)^\s*(?:"
        r"corrigendum|amendments?|deadline"
        r"|submission\s+deadline"
        r"|turnover\s+requirement"
        r"|experience\s+requirement"
        r")\s*:?"
    )

    in_document_section = False

    for raw_line in lines:
        line = clean(raw_line)

        if not line:
            continue

        if document_heading.match(line):
            in_document_section = True
            continue

        if in_document_section and stop_heading.match(line):
            break

        if in_document_section:
            item = re.sub(
                r"^\s*(?:\d+\s*[.)]|[-*•])\s*",
                "",
                line,
            )

            item = clean(item)

            if item:
                documents.append(item[:250])

    # Fallback if no explicit document section was found.
    if not documents:
        document_keywords = re.compile(
            r"(?i)\b(?:"
            r"registration certificate|PAN card"
            r"|GST registration|Udyam registration"
            r"|audited financial statements"
            r"|turnover certificate|work orders?"
            r"|work completion certificate"
            r"|EMD payment proof|technical bid"
            r"|financial bid|declaration"
            r"|experience certificate"
            r"|authorization letter|power of attorney"
            r"|affidavit"
            r")\b"
        )

        for line in lines:
            if document_keywords.search(line):
                documents.append(clean(line)[:250])

    documents = unique(documents)[:50]

    # -----------------------------------------------------
    # F. CORRIGENDUM / AMENDMENTS
    # -----------------------------------------------------

    corrigendum = None

    for index, line in enumerate(lines):
        if re.search(r"(?i)\bcorrigendum\b", line):
            collected = [clean(line)]

            for following in lines[index + 1:index + 3]:
                following = clean(following)

                if not following:
                    continue

                if stop_heading.match(following):
                    break

                collected.append(following)

            corrigendum = " | ".join(unique(collected))[:400]
            break

    if not corrigendum:
        if re.search(
            r"(?i)\b(?:amendment|amendments|revised tender)\b",
            text,
        ):
            corrigendum = (
                "Amendment mentioned. Check the latest official "
                "tender notice and corrigendum."
            )
        else:
            corrigendum = NOT_FOUND

    # -----------------------------------------------------
    # G. RETURN ANALYSIS
    # -----------------------------------------------------

    return {
        "possible_deadline": deadline,
        "possible_emd": emd,
        "turnover": turnover,
        "experience": experience,
        "documents": documents,
        "corrigendum": corrigendum,
    }


# =========================================================
# 7. ROOT ENDPOINT
# =========================================================

@app.get("/")
def root():
    return {
        "name": "TenderPilot AI API",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }


# =========================================================
# 8. HEALTH CHECK
# =========================================================

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "TenderPilot AI API",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =========================================================
# 9. DEMO TENDER LIST
# =========================================================

@app.get("/api/tenders")
def get_tenders():
    return {
        "success": True,
        "mode": "synthetic_demo",
        "count": len(DEMO_TENDERS),
        "tenders": DEMO_TENDERS,
        "notice": (
            "These are synthetic demonstration records, "
            "not verified live government tenders."
        ),
    }


# =========================================================
# 10. ANALYZE TENDER TEXT
# =========================================================

@app.post("/api/analyze")
def analyze_tender(request: AnalyzeRequest):
    try:
        findings = extract_findings(request.text)

        return {
            "success": True,
            "analysis_mode": "LOCAL_RULE_BASED",
            "model": None,
            "findings": findings,
            "verification_required": True,
            "notice": (
                "Preliminary extraction only. Verify all dates, "
                "amounts, eligibility conditions and corrigenda "
                "against the latest official tender documents."
            ),
        }

    except Exception as error:
        # Avoid exposing internal exception details to API clients.
        print(f"Tender analysis error: {type(error).__name__}")

        raise HTTPException(
            status_code=500,
            detail="Tender analysis failed. Please check the input.",
        )
