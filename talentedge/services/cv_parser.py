import re
from io import BytesIO


def parse_cv(file_bytes: bytes, filename: str) -> str:
    """Extract text from CV file (PDF, DOCX, TXT)."""
    name = filename.lower()
    if name.endswith(".pdf"):
        return _parse_pdf(file_bytes)
    elif name.endswith(".docx"):
        return _parse_docx(file_bytes)
    elif name.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="ignore").strip()
    return file_bytes.decode("utf-8", errors="ignore").strip()


def _parse_pdf(data: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(BytesIO(data)) as pdf:
            parts = [p.extract_text() for p in pdf.pages if p.extract_text()]
        if parts:
            return "\n".join(parts).strip()
    except Exception:
        pass
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(BytesIO(data))
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        if text.strip():
            return text.strip()
    except Exception:
        pass
    return ""


def _parse_docx(data: bytes) -> str:
    try:
        import docx
        doc = docx.Document(BytesIO(data))
        text = "\n".join([p.text for p in doc.paragraphs])
        if text.strip():
            return text.strip()
    except Exception:
        pass
    try:
        import zipfile
        with zipfile.ZipFile(BytesIO(data)) as zf:
            if "word/document.xml" in zf.namelist():
                xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
                clean = re.sub(r"<[^>]+>", " ", xml)
                clean = re.sub(r"\s+", " ", clean).strip()
                if len(clean) > 20:
                    return clean
    except Exception:
        pass
    return ""


def extract_email(text: str) -> str:
    if not text:
        return ""
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}', text)
    skip = ["noreply","info@","support@","hr@","admin@","contact@","sales@","hello@"]
    ok_tlds = {"com","org","net","edu","io","in","co","uk","us","ca","au","de","fr","ai","dev","tech","me"}
    for e in emails:
        el = e.lower()
        if any(el.startswith(s) for s in skip):
            continue
        parts = el.split("@")
        if len(parts) != 2 or len(parts[0]) < 2:
            continue
        dp = parts[1].split(".")
        if len(dp) < 2 or dp[-1] not in ok_tlds:
            continue
        return e
    return ""


def extract_name(text: str) -> str:
    if not text:
        return ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # Strategy 1: Label
    for line in lines[:20]:
        m = re.match(r'(?:full\s*name|name|candidate\s*name)\s*[:;\-]\s*(.+)', line, re.IGNORECASE)
        if m:
            nm = m.group(1).strip().strip('.,;:')
            if 2 <= len(nm.split()) <= 5 and not re.search(r'\d', nm):
                return nm
    # Strategy 2: First name-like line
    skip_p = [r'@', r'https?://|www\.', r'\d{5,}',
              r'(?i)\b(?:resume|curriculum|vitae|cv|objective|summary|profile|experience)\b',
              r'(?i)\b(?:phone|tel|mobile|cell)\b', r'(?i)\b(?:linkedin|github)\b', r'[|/\\\\]']
    for line in lines[:15]:
        if any(re.search(p, line) for p in skip_p):
            continue
        test = line
        if '@' in line:
            test = re.sub(r'\S+@\S+', '', line).strip()
            test = re.sub(r'(?i)\b(?:email|e-mail)\s*[:;-]?\s*', '', test).strip()
        if len(test) > 45 or len(test) < 3:
            continue
        test = re.sub(r'\s+', ' ', test).strip()
        words = test.split()
        if 2 <= len(words) <= 4:
            if all(w[0].isupper() for w in words if w):
                if all(re.match(r"^[A-Za-z'.\-]+$", w) for w in words):
                    return test
    return ""
