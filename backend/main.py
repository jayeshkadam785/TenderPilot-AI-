def extract_findings(text):
    """
    Rule-based fallback for tender analysis.

    Extracts:
    - Tender deadline
    - EMD / bid security
    - Turnover requirements
    - Experience requirements
    - Required documents
    - Corrigendum clues

    Important:
    These are preliminary text extractions, not official verification.
    """

    if not isinstance(text, str):
        text = ""

    text = text.strip()

    if not text:
        return {
            "possible_deadline": "Not stated in supplied text",
            "possible_emd": "Not stated in supplied text",
            "turnover": "Not stated in supplied text",
            "experience": "Not stated in supplied text",
            "documents": [],
            "corrigendum": "Not stated in supplied text",
        }

    # --------------------------------------------------
    # Helper: remove unnecessary whitespace
    # --------------------------------------------------

    def clean(value):
        return re.sub(r"\s+", " ", str(value)).strip(" \t\r\n:;,-")

    # --------------------------------------------------
    # 1. DEADLINE EXTRACTION
    # --------------------------------------------------

    deadline_patterns = [
        # Example: Deadline: 15 November 2026, 5:00 PM IST
        r"(?im)^\s*(?:bid\s+submission\s+)?"
        r"(?:submission\s+)?(?:deadline|closing\s+date|"
        r"last\s+date|due\s+date|bid\s+end\s+date)"
        r"\s*(?:for\s+submission)?\s*[:=\-]?\s*"
        r"([^\n\r]{3,120})",

        # Example: Tender closes on 15 November 2026
        r"(?i)\b(?:closes?|closing|submit\s+by|"
        r"last\s+date\s+for\s+submission)"
        r"\s*(?:on|is|:|-)?\s*"
        r"([^\n\r]{3,100})",

        # Example: 15 November 2026
        r"(?i)\b\d{1,2}\s+"
        r"(?:January|February|March|April|May|June|July|"
        r"August|September|October|November|December)"
        r"\s+\d{4}"
        r"(?:[,\s]+(?:at\s+)?\d{1,2}(?::\d{2})?"
        r"\s*(?:AM|PM|IST)?)?",
    ]

    deadline = None

    for pattern in deadline_patterns:
        match = re.search(pattern, text)

        if match:
            candidate = clean(match.group(1) if match.lastindex else match.group(0))

            if candidate and len(candidate) <= 120:
                deadline = candidate
                break

    if not deadline:
        deadline = "Not stated in supplied text"

    # --------------------------------------------------
    # 2. EMD / BID SECURITY EXTRACTION
    # --------------------------------------------------

    amount_pattern = (
        r"(?:₹|Rs\.?\s*|INR\s*)?"
        r"\s*\d[\d,]*(?:\.\d+)?"
        r"(?:\s*(?:crore|crores|lakh|lakhs|"
        r"million|thousand))?"
    )

    emd_patterns = [
        # Example: EMD: ₹50,000
        r"(?i)\b(?:EMD|earnest\s+money\s+deposit|"
        r"bid\s+security|earnest\s+money)"
        r"\s*(?:\([^)]{0,40}\))?"
        r"\s*(?:amount)?\s*(?:is|of|:|=|-)?\s*"
        r"(" + amount_pattern + r")",

        # Example: Earnest Money Deposit (EMD): ₹50,000
        r"(?i)\bearnest\s+money\s+deposit"
        r"\s*\(\s*EMD\s*\)\s*[:=\-]?\s*"
        r"(" + amount_pattern + r")",

        # Example: ₹50,000 EMD
        r"(" + amount_pattern + r")"
        r"\s*(?:as\s+)?(?:EMD|bid\s+security)"
        r"\b",
    ]

    emd = None

    for pattern in emd_patterns:
        match = re.search(pattern, text)

        if match:
            candidate = clean(match.group(1))

            if candidate:
                emd = candidate
                break

    if not emd:
        # Preserve the clue if the amount could not be extracted.
        if re.search(
            r"(?i)\b(?:EMD|earnest\s+money\s+deposit|"
            r"bid\s+security|earnest\s+money)\b",
            text,
        ):
            emd = "Mentioned; amount not extracted"
        else:
            emd = "Not stated in supplied text"

    # --------------------------------------------------
    # 3. TURNOVER EXTRACTION
    # --------------------------------------------------

    turnover_patterns = [
        r"(?is)\b(?:minimum\s+)?(?:annual\s+)?"
        r"turnover(?:\s+requirement)?\s*[:\-]?\s*"
        r"(.{0,250}?)(?=\n\s*(?:experience|"
        r"required\s+documents|documents|corrigendum|"
        r"EMD|deadline)\b|\Z)",

        r"(?is)\b(?:average\s+)?annual\s+turnover\b"
        r"(.{0,200}?)(?=\n\s*(?:experience|"
        r"required\s+documents|documents|corrigendum)\b|\Z)",
    ]

    turnover = None

    for pattern in turnover_patterns:
        match = re.search(pattern, text)

        if match:
            candidate = clean(match.group(0))

            if candidate:
                turnover = candidate[:300]
                break

    if not turnover:
        turnover = "Not stated in supplied text"

    # --------------------------------------------------
    # 4. EXPERIENCE EXTRACTION
    # --------------------------------------------------

    experience_patterns = [
        r"(?is)\bexperience(?:\s+requirement)?\s*[:\-]?\s*"
        r"(.{0,250}?)(?=\n\s*(?:required\s+documents|"
        r"documents|corrigendum|EMD|deadline|"
        r"turnover)\b|\Z)",

        r"(?is)\b(?:minimum\s+)?\d+\s+years?"
        r"\s+of\s+experience\b"
        r"([^\n\r]{0,200})",
    ]

    experience = None

    for pattern in experience_patterns:
        match = re.search(pattern, text)

        if match:
            candidate = clean(match.group(0))

            if candidate:
                experience = candidate[:300]
                break

    if not experience:
        experience = "Not stated in supplied text"

    # --------------------------------------------------
    # 5. REQUIRED DOCUMENTS EXTRACTION
    # --------------------------------------------------

    documents = []

    document_section_patterns = [
        r"(?is)(?:required\s+documents|"
        r"documents\s+required|"
        r"list\s+of\s+documents|"
        r"document\s+checklist|"
        r"supporting\s+documents)\s*[:\-]?\s*"
        r"(.*?)(?=\n\s*(?:corrigendum|"
        r"amendments?|deadline|"
        r"submission\s+deadline|"
        r"turnover\s+requirement|"
        r"experience\s+requirement)\s*:?\s*(?:\n|$)|\Z)"
    ]

    document_section = None

    for pattern in document_section_patterns:
        match = re.search(pattern, text)

        if match:
            document_section = match.group(1)
            break

    if document_section:
        for line in document_section.splitlines():
            line = clean(line)

            if not line:
                continue

            # Remove numbering such as 1., 2), or bullet symbols.
            line = re.sub(
                r"^\s*(?:(?:\d+|[a-zA-Z])[.)]\s*|[-*•]\s*)",
                "",
                line,
            )

            line = clean(line)

            if not line:
                continue

            # Ignore section labels rather than treating them as documents.
            if re.match(
                r"(?i)^(?:corrigendum|amendments?|deadline|"
                r"turnover requirement|experience requirement)\s*:",
                line,
            ):
                break

            # Keep only sensible-length document entries.
            if len(line) > 250:
                line = line[:250].rstrip()

            if line and line.lower() not in {
                item.lower() for item in documents
            }:
                documents.append(line)

    # Fallback: detect document-related clues across the whole notice.
    # This does not guarantee a complete official checklist.
    if not documents:
        document_keywords = [
            "company registration certificate",
            "registration certificate",
            "pan card",
            "pan",
            "gst registration certificate",
            "gst registration",
            "udyam registration",
            "audited financial statements",
            "financial statements",
            "ca-certified turnover certificate",
            "turnover certificate",
            "work orders",
            "work order",
            "work completion certificates",
            "work completion certificate",
            "emd payment proof",
            "technical bid",
            "financial bid",
            "declaration accepting tender conditions",
            "declaration",
            "experience certificate",
            "authorization letter",
            "power of attorney",
            "affidavit",
        ]

        for line in text.splitlines():
            line_clean = clean(line)

            if not line_clean:
                continue

            normalized = line_clean.lower()

            if any(keyword in normalized for keyword in document_keywords):
                line_clean = re.sub(
                    r"^\s*(?:(?:\d+|[a-zA-Z])[.)]\s*|[-*•]\s*)",
                    "",
                    line_clean,
                )

                if line_clean and line_clean.lower() not in {
                    item.lower() for item in documents
                }:
                    documents.append(line_clean[:250])

    # --------------------------------------------------
    # 6. CORRIGENDUM EXTRACTION
    # --------------------------------------------------

    corrigendum_patterns = [
        r"(?is)\bcorrigendum\b\s*[:\-]?\s*"
        r"(.{0,400}?)(?=\n\s*(?:required\s+documents|"
        r"documents|deadline|EMD|turnover|experience)\b|\Z)",

        r"(?is)\b(?:amendment|amendments|"
        r"tender\s+revised|revised\s+tender)\b"
        r"([^\n\r]{0,300})",
    ]

    corrigendum = None

    for pattern in corrigendum_patterns:
        match = re.search(pattern, text)

        if match:
            candidate = clean(match.group(0))

            if candidate:
                corrigendum = candidate[:400]
                break

    if not corrigendum:
        if re.search(
            r"(?i)\b(?:corrigendum|amendment|"
            r"amendments|revised\s+tender)\b",
            text,
        ):
            corrigendum = (
                "Mentioned; check the official tender portal "
                "for amendments and deadline changes."
            )
        else:
            corrigendum = "Not stated in supplied text"

    # --------------------------------------------------
    # 7. FINAL RESULT
    # --------------------------------------------------

    return {
        "possible_deadline": deadline,
        "possible_emd": emd,
        "turnover": turnover,
        "experience": experience,
        "documents": documents,
        "corrigendum": corrigendum,
    }
