def extract_findings(text):
    """
    Rule-based tender extraction fallback.

    Extracts:
    - Deadline and time
    - EMD / bid security amount
    - Turnover requirement
    - Experience requirement
    - Required documents
    - Corrigendum clues

    Extracted information is preliminary and must be verified
    against the latest official tender notice.
    """

    if not isinstance(text, str):
        text = ""

    text = text.strip()

    not_found = "Not stated in supplied text"

    if not text:
        return {
            "possible_deadline": not_found,
            "possible_emd": not_found,
            "turnover": not_found,
            "experience": not_found,
            "documents": [],
            "corrigendum": not_found,
        }

    def clean(value):
        value = str(value)
        value = re.sub(r"[ \t]+", " ", value)
        return value.strip(" \t\r\n:;,-")

    def unique(items):
        result = []
        seen = set()

        for item in items:
            item = clean(item)

            if item and item.lower() not in seen:
                result.append(item)
                seen.add(item.lower())

        return result

    # --------------------------------------------------
    # 1. DEADLINE EXTRACTION
    # --------------------------------------------------

    date_pattern = (
        r"\d{1,2}\s+"
        r"(?:January|February|March|April|May|June|July|"
        r"August|September|October|November|December)"
        r"\s+\d{4}"
        r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    )

    time_pattern = (
        r"(?:,\s*|\s+)?"
        r"(?:at\s+)?"
        r"\d{1,2}:\d{2}\s*(?:AM|PM)"
        r"(?:\s*(?:IST|UTC))?"
        r"|\s+\d{1,2}\s*(?:AM|PM)"
        r"(?:\s*(?:IST|UTC))?"
    )

    deadline = None

    deadline_labels = re.compile(
        r"(?im)^\s*"
        r"(?:bid\s+submission\s+|submission\s+)?"
        r"(?:deadline|closing\s+date|last\s+date|"
        r"due\s+date|bid\s+end\s+date)"
        r"\s*(?::|=|-)?\s*(.+)$"
    )

    for line in text.splitlines():
        match = deadline_labels.search(line)

        if not match:
            continue

        value = clean(match.group(1))

        date_match = re.search(date_pattern, value, re.I)

        if date_match:
            candidate = date_match.group(0)

            remainder = value[date_match.end():]

            time_match = re.search(
                r"\b\d{1,2}:\d{2}\s*(?:AM|PM)"
                r"(?:\s*(?:IST|UTC))?"
                r"|\b\d{1,2}\s*(?:AM|PM)"
                r"(?:\s*(?:IST|UTC))?",
                remainder,
                re.I,
            )

            if time_match:
                candidate += ", " + clean(time_match.group(0))

            deadline = candidate
            break

    if not deadline:
        match = re.search(date_pattern, text, re.I)

        if match:
            deadline = match.group(0)

            remainder = text[match.end():match.end() + 60]

            time_match = re.search(
                r"\b\d{1,2}:\d{2}\s*(?:AM|PM)"
                r"(?:\s*(?:IST|UTC))?"
                r"|\b\d{1,2}\s*(?:AM|PM)"
                r"(?:\s*(?:IST|UTC))?",
                remainder,
                re.I,
            )

            if time_match:
                deadline += ", " + clean(time_match.group(0))

    if not deadline:
        deadline = not_found

    # --------------------------------------------------
    # 2. EMD / BID SECURITY AMOUNT
    # --------------------------------------------------

    amount_pattern = (
        r"(?:₹\s*|Rs\.?\s*|INR\s*)?"
        r"\d[\d,]*(?:\.\d+)?"
        r"(?:\s*(?:crores?|lakhs?|millions?|thousands?))?"
    )

    emd = None

    # Match the amount on the same line as the EMD label.
    for line in text.splitlines():
        if not re.search(
            r"(?i)\b(?:EMD|earnest\s+money\s+deposit|"
            r"bid\s+security|earnest\s+money)\b",
            line,
        ):
            continue

        match = re.search(amount_pattern, line)

        if match:
            candidate = clean(match.group(0))

            if re.search(r"\d", candidate):
                emd = candidate
                break

    if not emd:
        if re.search(
            r"(?i)\b(?:EMD|earnest\s+money\s+deposit|"
            r"bid\s+security|earnest\s+money)\b",
            text,
        ):
            emd = "Mentioned; amount not extracted"
        else:
            emd = not_found

    # --------------------------------------------------
    # 3. TURNOVER REQUIREMENT
    # --------------------------------------------------

    turnover_lines = []

    for line in text.splitlines():
        if re.search(r"(?i)\bturnover\b", line):
            turnover_lines.append(clean(line))

    # Include the following lines when a turnover heading
    # is followed by the actual requirement.
    lines = text.splitlines()

    for index, line in enumerate(lines):
        if re.search(
            r"(?i)\bturnover\s+requirement\b",
            line,
        ):
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
        else not_found
    )

    # --------------------------------------------------
    # 4. EXPERIENCE REQUIREMENT
    # --------------------------------------------------

    experience_lines = []

    for line in text.splitlines():
        if re.search(
            r"(?i)\bexperience(?:\s+requirement)?\b",
            line,
        ):
            experience_lines.append(clean(line))

    for index, line in enumerate(lines):
        if re.search(
            r"(?i)\bexperience\s+requirement\b",
            line,
        ):
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
        else not_found
    )

    # --------------------------------------------------
    # 5. REQUIRED DOCUMENTS
    # --------------------------------------------------

    documents = []

    document_heading = re.compile(
        r"(?i)^\s*(?:required\s+documents|"
        r"documents\s+required|list\s+of\s+documents|"
        r"document\s+checklist|supporting\s+documents)"
        r"\s*:?\s*$"
    )

    stop_heading = re.compile(
        r"(?i)^\s*(?:corrigendum|amendments?|"
        r"deadline|submission\s+deadline|"
        r"turnover\s+requirement|"
        r"experience\s+requirement)\s*:?"
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
            # Remove numbering such as 1., 2), or bullets.
            item = re.sub(
                r"^\s*(?:\d+\s*[.)]|[-*•])\s*",
                "",
                line,
            )

            item = clean(item)

            # Avoid interpreting a heading as a document.
            if item and not re.match(
                r"(?i)^(?:department|tender title|"
                r"deadline|EMD|turnover requirement|"
                r"experience requirement)\s*:",
                item,
            ):
                documents.append(item[:250])

    documents = unique(documents)

    # If no explicit document section exists, extract
    # lines containing common document-related keywords.
    if not documents:
        document_keywords = re.compile(
            r"(?i)\b(?:registration certificate|PAN card|"
            r"GST registration|Udyam registration|"
            r"audited financial statements|"
            r"turnover certificate|work orders?|"
            r"work completion certificate|"
            r"EMD payment proof|technical bid|"
            r"financial bid|declaration|"
            r"experience certificate|authorization letter|"
            r"power of attorney|affidavit)\b"
        )

        for line in lines:
            line = clean(line)

            if document_keywords.search(line):
                item = re.sub(
                    r"^\s*(?:\d+\s*[.)]|[-*•])\s*",
                    "",
                    line,
                )

                if item:
                    documents.append(item[:250])

        documents = unique(documents)

    # --------------------------------------------------
    # 6. CORRIGENDUM
    # --------------------------------------------------

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
                "Amendment mentioned; check the official "
                "tender portal for updates."
            )
        else:
            corrigendum = not_found

    # --------------------------------------------------
    # 7. RETURN FINDINGS
    # --------------------------------------------------

    return {
        "possible_deadline": deadline,
        "possible_emd": emd,
        "turnover": turnover,
        "experience": experience,
        "documents": documents,
        "corrigendum": corrigendum,
    }
