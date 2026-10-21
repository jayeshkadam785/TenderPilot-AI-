from main import extract_findings

text = (
"Tender for website development. "
"Bid submission deadline: 25 October 2026. "
"EMD: Rs 50000. "
"Minimum annual turnover: Rs 2000000. "
"Minimum experience: 2 years. "
"Required documents: GST certificate, PAN card, "
"company registration certificate."
)

result = extract_findings(text)

for key, value in result.items():
print(f"{key}: {value}")
