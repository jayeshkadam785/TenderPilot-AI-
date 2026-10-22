import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any              
from html.parser import HTMLParser 
from urllib.parse import urljoin
from urllib.request import Request, urlopen 

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

    turnover = NOT_FOUND

    turnover_pattern = re.compile(
        r"(?i)\b(?:"
        r"minimum\s+annual\s+turnover"
        r"|annual\s+turnover"
        r"|minimum\s+turnover"
        r"|turnover\s+requirement"
        r"|turnover"
        r")\b"
        r"[^.\n]{0,40}?"
        r"(?:₹|Rs\.?|INR)?\s*"
        r"([\d,]+(?:\.\d+)?)"
        r"(?:\s*(crores?|lakhs?|millions?|thousands?))?"
    )

    turnover_match = turnover_pattern.search(text)

    if turnover_match:
        amount = turnover_match.group(1)
        unit = turnover_match.group(2) or ""
        currency = ""

        prefix = text[
            max(0, turnover_match.start() - 10):
            turnover_match.start()
        ]

        if re.search(r"₹|Rs\.?|INR", prefix, re.I):
            currency = "Rs "

        turnover = clean(
            f"{currency}{amount} {unit}".strip()
        )

    # -----------------------------------------------------
    # D. EXPERIENCE REQUIREMENT
    # -----------------------------------------------------

    experience = NOT_FOUND

    experience_pattern = re.compile(
        r"(?i)\b(?:"
        r"minimum\s+work\s+experience"
        r"|minimum\s+experience"
        r"|similar[- ]work\s+experience"
        r"|experience\s+requirement"
        r"|experience"
        r")\b"
        r"[^.\n]{0,40}?"
        r"(\d+(?:\.\d+)?\s*"
        r"(?:years?|yrs?|months?))"
    )

    experience_match = experience_pattern.search(text)

    if experience_match:
        experience = clean(experience_match.group(1))

    # -----------------------------------------------------
    # E. REQUIRED DOCUMENTS
    # -----------------------------------------------------

    documents = []

    document_pattern = re.compile(
        r"(?is)\b(?:"
        r"required\s+documents"
        r"|documents\s+required"
        r"|list\s+of\s+documents"
        r"|document\s+checklist"
        r"|supporting\s+documents"
        r")\s*[:=\-]\s*(.*?)"
        r"(?=\b(?:corrigendum|amendment|"
        r"bid\s+submission\s+deadline|"
        r"submission\s+deadline|"
        r"minimum\s+annual\s+turnover|"
        r"minimum\s+experience)\b|$)"
    )

    document_match = document_pattern.search(text)

    if document_match:
        document_text = document_match.group(1)

        items = re.split(
            r"\s*(?:,|;|\n|\band\b)\s*",
            document_text,
            flags=re.IGNORECASE
        )

        for item in items:
            item = re.sub(
                r"^\s*(?:\d+\s*[.)]|[-*•])\s*",
                "",
                item
            )

            item = clean(item).rstrip(".")

            if item:
                documents.append(item)

    if not documents:
        document_keywords = re.compile(
            r"(?i)\b(?:"
            r"GST certificate"
            r"|GST registration certificate"
            r"|PAN card"
            r"|company registration certificate"
            r"|Udyam registration"
            r"|audited financial statements"
            r"|turnover certificate"
            r"|work order"
            r"|work completion certificate"
            r"|experience certificate"
            r"|EMD payment proof"
            r"|technical bid"
            r"|financial bid"
            r"|authorization letter"
            r"|power of attorney"
            r"|affidavit"
            r")\b"
        )

        for match in document_keywords.finditer(text):
            documents.append(clean(match.group(0)))

    documents = unique(documents)[:50]

    # -----------------------------------------------------
    # F. CORRIGENDUM / AMENDMENTS
    # -----------------------------------------------------

    corrigendum = None

    stop_heading = re.compile(
        r"(?i)^(?:deadline|bid submission|submission deadline|"
        r"minimum annual turnover|minimum experience|"
        r"required documents|eligibility criteria)\b"
    )

    for index, line in enumerate(lines):
        if re.search(r"(?i)\b(?:corrigendum|amendment|amendments)\b", line):
            collected = []

            heading_match = re.search(
                r"(?i)\b(?:corrigendum|amendment|amendments)\b\s*[:\-]?\s*(.*)",
                line,
            )

            if heading_match:
                heading_text = clean(heading_match.group(1))
                if heading_text:
                    collected.append(heading_text)

            for following in lines[index + 1:index + 4]:
                following = clean(following)

                if not following:
                    continue

                if stop_heading.match(following):
                    break

                collected.append(following)

            corrigendum = " | ".join(unique(collected))[:400]

            if not corrigendum:
                corrigendum = (
                    "Corrigendum mentioned. Check the latest official "
                    "tender notice for amendment details."
                )

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
# LIVE GOVERNMENT TENDER FETCHING
# =========================================================

LIVE_TENDER_SOURCE = (
    "https://www.eprocure.gov.in/epublish/app?service=home"
)


class TenderHTMLParser(HTMLParser):
    """Parse public tender tables from the government portal."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "tr":
            self.row = []

        elif tag in ("td", "th") and self.row is not None:
            self.cell = {"text": [], "links": []}

        elif tag == "a" and self.cell is not None:
            href = attrs.get("href")
            if href:
                self.cell["links"].append(href)

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"].append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            value = " ".join(
                "".join(self.cell["text"]).split()
            )

            self.row.append({
                "text": value,
                "links": self.cell["links"]
            })

            self.cell = None

        elif tag == "tr" and self.row is not None:
            if self.row:
                self.rows.append(self.row)

            self.row = None
            self.cell = None


def parse_portal_date(value):
    """Convert common government portal date formats."""

    value = " ".join(str(value or "").split())

    formats = [
        "%d-%b-%Y %I:%M %p",
        "%d-%B-%Y %I:%M %p",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)

            india_timezone = timezone(
                timedelta(hours=5, minutes=30)
            )

            return parsed.replace(
                tzinfo=india_timezone
            ).isoformat()

        except ValueError:
            continue

    return None


def fetch_live_tenders(query="", limit=20):
    """Fetch public tender listings from CPPP ePublishing."""

    request = Request(
        LIVE_TENDER_SOURCE,
        headers={
            "User-Agent": "TenderPilotAI/1.0",
            "Accept": "text/html",
        },
    )

    with urlopen(request, timeout=8) as response:
        html = response.read(
            2_500_000
        ).decode("utf-8", errors="replace")

    parser = TenderHTMLParser()
    parser.feed(html)

    rows = parser.rows

    # Locate the tender table header.
    header_index = None
    columns = {}

    for i, row in enumerate(rows):
        labels = [
            cell["text"].lower().strip()
            for cell in row
        ]

        title_col = next(
            (
                j for j, label in enumerate(labels)
                if "tender title" in label
                or label == "title"
            ),
            None,
        )

        reference_col = next(
            (
                j for j, label in enumerate(labels)
                if "reference no" in label
                or "reference number" in label
            ),
            None,
        )

        closing_col = next(
            (
                j for j, label in enumerate(labels)
                if "closing date" in label
            ),
            None,
        )

        if (
            title_col is not None
            and reference_col is not None
            and closing_col is not None
        ):
            header_index = i

            columns = {
                "title": title_col,
                "reference": reference_col,
                "closing": closing_col,
            }

            break

    if header_index is None:
        raise ValueError(
            "Could not identify the tender table on the portal."
        )

    results = []

    for row in rows[header_index + 1:]:

        if max(columns.values()) >= len(row):
            continue

        title_cell = row[columns["title"]]

        title = title_cell["text"].strip()
        reference = row[columns["reference"]]["text"].strip()
        closing = row[columns["closing"]]["text"].strip()

        if not title or not closing:
            continue

        if query and query.casefold() not in (
            title + " " + reference
        ).casefold():
            continue

        source_url = LIVE_TENDER_SOURCE

        if title_cell["links"]:
            candidate_url = urljoin(
                LIVE_TENDER_SOURCE,
                title_cell["links"][0],
            )

            if candidate_url.startswith(("https://", "http://")):
                source_url = candidate_url

        results.append({
            "id": reference or f"CPPP-{len(results) + 1}",
            "title": title,
            "reference_number": reference or None,
            "department": None,
            "category": None,
            "location": "India",
            "estimated_value": None,
            "closing_date": closing,
            "closing_date_iso": parse_portal_date(closing),
            "source_name": "Government of India CPPP",
            "source_url": source_url,
            "verified": False,
        })

        if len(results) >= limit:
            break

    return results


@app.get("/api/tenders/live")
def get_live_tenders(q: str = "", limit: int = 20):
    """Return live public tender listings."""

    limit = max(1, min(limit, 50))

    try:
        tenders = fetch_live_tenders(
            query=q.strip(),
            limit=limit,
        )

        return {
            "success": True,
            "mode": "live_public_portal_listing",
            "source_name": "Government of India CPPP ePublishing",
            "source_url": LIVE_TENDER_SOURCE,
            "count": len(tenders),
            "tenders": tenders,
            "notice": (
                "Public portal listings only. Verify the official "
                "tender documents, eligibility, EMD and latest "
                "corrigenda before making decisions."
            ),
        }

    except Exception as error:
        print(
            "Live tender fetch error:",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Could not fetch live tenders from the government "
                "portal. Please retry later or open the official source."
            ),
        )
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
# =========================================================
# 11. MSME ELIGIBILITY MATCHING AGENT
# =========================================================

class BusinessProfile(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=100)
    region: str = Field(..., min_length=1, max_length=100)

    min_budget: float = Field(default=0, ge=0)
    max_budget: float = Field(..., gt=0)

    annual_turnover: float | None = Field(default=None, ge=0)
    similar_work_years: float | None = Field(default=None, ge=0)
    msme_registered: bool | None = None


class EligibilityMatchRequest(BaseModel):
    profile: BusinessProfile

    tenders: list[dict[str, Any]] | None = None


def normalize_text(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value or "").lower()
    ).strip()


def score_tender_for_business(
    profile: BusinessProfile,
    tender: dict[str, Any]
) -> dict[str, Any]:

    score = 0
    checks = []
    reasons = []
    warnings = []

    def add_check(name, status, detail, points):
        nonlocal score

        score += points

        checks.append({
            "check": name,
            "status": status,
            "detail": detail,
            "points": points
        })

    # 1. BUSINESS CATEGORY

    category = normalize_text(profile.category)

    tender_category = normalize_text(
        tender.get("category", "")
    )

    tender_title = normalize_text(
        tender.get("title", "")
    )

    tokens = [
        word for word in category.split()
        if len(word) > 2
    ]

    category_match = bool(
        tokens and any(
            word in tender_category
            or word in tender_title
            for word in tokens
        )
    )

    add_check(
        "Business category",
        "match" if category_match else "review",
        (
            "Business category appears relevant."
            if category_match
            else "Manually review the tender scope."
        ),
        30 if category_match else 8
    )

    if category_match:
        reasons.append(
            "Business category appears relevant."
        )

    # 2. LOCATION

    business_region = normalize_text(profile.region)

    tender_region = normalize_text(
        tender.get("location", "")
    )

    region_match = bool(
        business_region
        and tender_region
        and (
            business_region == tender_region
            or business_region in tender_region
            or tender_region in business_region
            or "india" in tender_region
        )
    )

    add_check(
        "Geographic coverage",
        "match" if region_match else "review",
        (
            "Location appears compatible."
            if region_match
            else "Check the official bidder-location rules."
        ),
        20 if region_match else 5
    )

    if region_match:
        reasons.append(
            "Location appears compatible."
        )

    # 3. TENDER VALUE

    try:
        value = float(
            tender["estimated_value"]
        ) if tender.get("estimated_value") is not None else None
    except (TypeError, ValueError):
        value = None

    if value is None:
        add_check(
            "Tender value",
            "unknown",
            "Tender value is not available.",
            5
        )

        warnings.append(
            "Tender value needs verification."
        )

    elif profile.min_budget <= value <= profile.max_budget:
        add_check(
            "Tender value",
            "match",
            f"Tender value ₹{value:,.0f} fits your budget.",
            20
        )

        reasons.append(
            "Tender value fits your selected budget."
        )

    else:
        add_check(
            "Tender value",
            "outside_range",
            f"Tender value ₹{value:,.0f} is outside your budget.",
            0
        )

        warnings.append(
            "Tender value is outside your selected budget."
        )

   ```python
    # 4. TURNOVER REQUIREMENT

    try:
        required_turnover = tender.get("minimum_turnover")
        required_turnover = (
            float(required_turnover)
            if required_turnover is not None
            else None
        )
    except (TypeError, ValueError):
        required_turnover = None

    if required_turnover is None:
        add_check(
            "Annual turnover",
            "not_verified",
            "Minimum turnover requirement is not available in the supplied tender record.",
            5
        )
        warnings.append(
            "Verify the minimum turnover requirement in the official tender."
        )

    elif profile.annual_turnover is None:
        add_check(
            "Annual turnover",
            "unknown",
            f"Required turnover: Rs {required_turnover:,.0f}. Business turnover not provided.",
            0
        )
        warnings.append(
            "Provide annual turnover to check this requirement."
        )

    elif profile.annual_turnover >= required_turnover:
        add_check(
            "Annual turnover",
            "match",
            f"Business turnover Rs {profile.annual_turnover:,.0f} meets the stated minimum Rs {required_turnover:,.0f}.",
            10
        )
        reasons.append(
            "Provided annual turnover meets the stated minimum."
        )

    else:
        add_check(
            "Annual turnover",
            "below_requirement",
            f"Business turnover Rs {profile.annual_turnover:,.0f} is below the stated minimum Rs {required_turnover:,.0f}.",
            0
        )
        warnings.append(
            "Business turnover is below the stated minimum requirement."
        )

    # 5. SIMILAR-WORK EXPERIENCE

    try:
        required_experience = tender.get(
            "minimum_experience_years"
        )
        required_experience = (
            float(required_experience)
            if required_experience is not None
            else None
        )
    except (TypeError, ValueError):
        required_experience = None

    if required_experience is None:
        add_check(
            "Similar-work experience",
            "not_verified",
            "Minimum experience requirement is not available in the supplied tender record.",
            5
        )
        warnings.append(
            "Verify the minimum experience requirement in the official tender."
        )

    elif profile.similar_work_years is None:
        add_check(
            "Similar-work experience",
            "unknown",
            f"Required experience: {required_experience:g} years. Business experience not provided.",
            0
        )
        warnings.append(
            "Provide similar-work experience to check this requirement."
        )

    elif profile.similar_work_years >= required_experience:
        add_check(
            "Similar-work experience",
            "match",
            f"Provided experience {profile.similar_work_years:g} years meets the stated minimum {required_experience:g} years.",
            10
        )
        reasons.append(
            "Provided similar-work experience meets the stated minimum."
        )

    else:
        add_check(
            "Similar-work experience",
            "below_requirement",
            f"Provided experience {profile.similar_work_years:g} years is below the stated minimum {required_experience:g} years.",
            0
        )
        warnings.append(
            "Similar-work experience is below the stated minimum requirement."
        )

```

    # 6. MSME REGISTRATION

    if profile.msme_registered is True:
        add_check(
            "MSME registration",
            "provided",
            "Verify the certificate and tender-specific benefits.",
            5
        )

        warnings.append(
            "MSME exemptions depend on the official tender conditions."
        )

    elif profile.msme_registered is False:
        add_check(
            "MSME registration",
            "not_registered",
            "Business profile says MSME registration is unavailable.",
            0
        )

    else:
        add_check(
            "MSME registration",
            "unknown",
            "Registration status was not provided.",
            2
        )

        warnings.append(
            "Provide your MSME registration status."
        )

    # 7. FINAL RESULT

    score = min(100, max(0, score))

    if score >= 75:
        label = "Strong potential match"
    elif score >= 50:
        label = "Review before applying"
    else:
        label = "Low apparent match"

    return {
        "tender_id": tender.get(
            "id", "USER-SUPPLIED"
        ),
        "title": tender.get(
            "title", "Untitled tender"
        ),
        "score": score,
        "match_label": label,
        "reasons": reasons,
        "checks": checks,
        "warnings": list(dict.fromkeys(warnings)),
        "source": tender.get(
            "source", "User-supplied record"
        ),
        "verified": False,
        "decision": "PRELIMINARY_SCREEN_ONLY"
    }


# =========================================================
# 12. ELIGIBILITY MATCH API
# =========================================================

@app.post("/api/eligibility-match")
def eligibility_match(
    request: EligibilityMatchRequest
):
    try:
        tender_records = (
            request.tenders
            if request.tenders is not None
            else DEMO_TENDERS
        )

        results = [
            score_tender_for_business(
                request.profile,
                tender
            )
            for tender in tender_records
        ]

        results.sort(
            key=lambda item: item["score"],
            reverse=True
        )

        return {
            "success": True,
            "agent": "MSME Eligibility Matching Agent",
            "mode": "RULE_BASED_PRELIMINARY_SCREEN",
            "business": request.profile.model_dump(),
            "count": len(results),
            "matches": results,
            "notice": (
                "Preliminary suitability screening only. "
                "Verify all mandatory eligibility requirements "
                "against the latest official tender documents."
            )
        }

    except Exception as error:
        print(
            f"Eligibility matching error: "
            f"{type(error).__name__}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Eligibility matching failed. "
                "Check the supplied profile and tender records."
            )
        )
