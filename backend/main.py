"""TenderPilot AI starter API.

This MVP uses transparent rule-based extraction for a local demo. It does not
verify official tender notices and must not be treated as legal/eligibility advice.
"""
from datetime import datetime, timezone
from typing import Optional
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="TenderPilot AI API",
    description="Starter API for tender discovery and notice analysis. Demo data only.",
    version="0.1.0",
)

# Replace the last entry with your real Vercel URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://tenderpilot-ai.vercel.app",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class AnalyzeRequest(BaseModel):
    title: str = Field(default="Untitled tender", max_length=300)
    notice_text: str = Field(min_length=10, max_length=100_000)
    source_url: Optional[str] = Field(default=None, max_length=2000)


def find_match(text: str, patterns: list[str]) -> Optional[re.Match]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match
    return None


def extract_findings(text: str) -> list[dict]:
    findings = []
    deadline = find_match(text, [
        r"(?:submission|bid|tender|closing|due)\s*(?:date|deadline|time)?\s*[:\-]?\s*((?:\d{1,2}[/-]){1,2}\d{2,4}(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)?)",
        r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)?)",
    ])
    if deadline:
        findings.append({"field": "possible_deadline", "value": deadline.group(1).strip(), "status": "UNVERIFIED", "evidence": deadline.group(0).strip()})
    else:
        findings.append({"field": "possible_deadline", "value": "Not found", "status": "MISSING", "evidence": "No recognizable deadline pattern found in pasted text."})

    emd = find_match(text, [
        r"(?:EMD|earnest money deposit|bid security)[^\n\r₹]{0,50}(₹\s?[\d,]+(?:\.\d{1,2})?)",
        r"(₹\s?[\d,]+(?:\.\d{1,2})?)[^\n\r]{0,40}(?:EMD|earnest money deposit|bid security)",
    ])
    if emd:
        findings.append({"field": "possible_emd", "value": emd.group(1).strip(), "status": "REVIEW_REQUIRED", "evidence": emd.group(0).strip()})
    elif re.search(r"\b(?:EMD|earnest money deposit|bid security)\b", text, re.I):
        findings.append({"field": "possible_emd", "value": "Mentioned; amount not extracted", "status": "REVIEW_REQUIRED", "evidence": "EMD/bid security phrase appears in the notice."})
    else:
        findings.append({"field": "possible_emd", "value": "Not found in pasted text", "status": "UNVERIFIED", "evidence": "Absence in pasted text does not prove EMD is not required."})

    requirements = [
        ("turnover", r"(?:annual\s+)?turnover[^\n\r.]{0,100}"),
        ("experience", r"(?:similar\s+work|experience|completed\s+works?)[^\n\r.]{0,120}"),
        ("documents", r"(?:GST|Udyam|PAN|work\s+order|annexure|technical\s+bid|financial\s+bid|certificate)[^\n\r.]{0,100}"),
        ("corrigendum", r"(?:corrigendum|amendment|extension\s+of\s+(?:bid|submission)|revised\s+deadline)[^\n\r.]{0,120}"),
    ]
    for name, pattern in requirements:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            snippets = list(dict.fromkeys(m.strip() for m in matches))[:3]
            findings.append({"field": name, "value": " | ".join(snippets), "status": "REVIEW_REQUIRED", "evidence": "Extracted from pasted notice text; check the official document."})
        else:
            findings.append({"field": name, "value": "Not detected", "status": "NOT_DETECTED", "evidence": "No matching phrase detected in the supplied text."})
    return findings


@app.get("/")
def root():
    return {"name": "TenderPilot AI API", "status": "running", "docs": "/docs", "data_mode": "demo/rule-based"}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "tenderpilot-api", "timestamp_utc": datetime.now(timezone.utc).isoformat()}


@app.get("/api/tenders")
def get_demo_tenders():
    # Clearly labelled synthetic examples; replace with permitted official data sources.
    return {
        "mode": "SYNTHETIC_DEMO_DATA",
        "tenders": [
            {"id": "DEMO-TP-001", "title": "IT Support and Maintenance Services", "region": "Maharashtra", "category": "IT Services", "estimated_value_inr": 2500000, "deadline": None, "deadline_status": "UNVERIFIED", "source_url": None},
            {"id": "DEMO-TP-002", "title": "Supply of Computer Equipment", "region": "Maharashtra", "category": "Hardware", "estimated_value_inr": 1800000, "deadline": None, "deadline_status": "UNVERIFIED", "source_url": None},
        ],
        "notice": "These are synthetic examples, not live government tenders.",
    }


@app.post("/api/analyze")
def analyze_notice(request: AnalyzeRequest):
    findings = extract_findings(request.notice_text)
    return {
        "title": request.title,
        "source_url": request.source_url,
        "analysis_mode": "LOCAL_RULE_BASED_PREVIEW",
        "officially_verified": False,
        "eligibility_decision": "NOT_DETERMINED",
        "findings": findings,
        "warnings": [
            "This is pattern-based extraction, not a verified AI/legal assessment.",
            "Confirm every requirement and deadline against the latest official tender notice and corrigenda.",
            "Do not infer eligibility from missing or unrecognized text.",
        ],
    }
