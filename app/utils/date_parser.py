import re
from datetime import datetime

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12
}

def extract_newspaper_date(filename):
    """Extracts date from newspaper filename.
    
    Supports:
      - DD-MM-YYYY / DD_MM_YYYY / DD.MM.YYYY (e.g. 01-08-2026, 01_08_2026, 01.08.2026)
      - YYYY-MM-DD / YYYY_MM_DD / YYYY.MM.DD (e.g. 2026-08-01, 2026_08_01, 2026.08.01)
      - DD-Mon-YYYY / DD_Mon_YYYY / DDMonYYYY (e.g. 01-Aug-2026, 01_Aug_2026, 01Aug2026)
      - D Month YYYY / DD Month YYYY (e.g. 1 August 2026, 01 August 2026)
      
    Returns tuple: (iso_date_str, formatted_label)
    Example: ('2026-08-01', '01 AUGUST 2026')
    If no date pattern found, returns: (None, 'DATE UNKNOWN')
    """
    if not filename:
        return None, "DATE UNKNOWN"

    fname = str(filename).strip()

    # Pattern 1: DD-Mon-YYYY or DD_Mon_YYYY or DDMonYYYY (e.g. 01-Aug-2026, 01_Aug_2026, 01Aug2026)
    p1 = re.search(r'(?:^|[^0-9a-zA-Z])(\d{1,2})[-_\s]?([a-zA-Z]{3,9})[-_\s]?(\d{4})(?:[^0-9a-zA-Z]|$)', fname)
    if p1:
        d_str, m_str, y_str = p1.groups()
        m_lower = m_str.lower()
        if m_lower in MONTH_MAP:
            try:
                dt = datetime(int(y_str), MONTH_MAP[m_lower], int(d_str))
                return dt.strftime("%Y-%m-%d"), dt.strftime("%d %B %Y").upper()
            except ValueError:
                pass

    # Pattern 2: D Month YYYY or DD Month YYYY (e.g. 1 August 2026, 01 August 2026)
    p2 = re.search(r'(?:^|[^0-9a-zA-Z])(\d{1,2})\s+([a-zA-Z]{3,9})\s+(\d{4})(?:[^0-9a-zA-Z]|$)', fname)
    if p2:
        d_str, m_str, y_str = p2.groups()
        m_lower = m_str.lower()
        if m_lower in MONTH_MAP:
            try:
                dt = datetime(int(y_str), MONTH_MAP[m_lower], int(d_str))
                return dt.strftime("%Y-%m-%d"), dt.strftime("%d %B %Y").upper()
            except ValueError:
                pass

    # Pattern 3: YYYY-MM-DD or YYYY_MM_DD or YYYY.MM.DD (e.g. 2026-08-01)
    p3 = re.search(r'(?:^|[^0-9])(\d{4})[-_\.](\d{1,2})[-_\.](\d{1,2})(?:[^0-9]|$)', fname)
    if p3:
        y_str, m_str, d_str = p3.groups()
        try:
            dt = datetime(int(y_str), int(m_str), int(d_str))
            return dt.strftime("%Y-%m-%d"), dt.strftime("%d %B %Y").upper()
        except ValueError:
            pass

    # Pattern 4: DD-MM-YYYY or DD_MM_YYYY or DD.MM.YYYY (e.g. 01-08-2026, 01_08_2026)
    p4 = re.search(r'(?:^|[^0-9])(\d{1,2})[-_\.](\d{1,2})[-_\.](\d{4})(?:[^0-9]|$)', fname)
    if p4:
        d_str, m_str, y_str = p4.groups()
        try:
            dt = datetime(int(y_str), int(m_str), int(d_str))
            return dt.strftime("%Y-%m-%d"), dt.strftime("%d %B %Y").upper()
        except ValueError:
            pass

    # Pattern 5: 8-digit DDMMYYYY (e.g. 04082026 -> 2026-08-04)
    p5 = re.search(r'(?:^|[^0-9])(\d{2})(\d{2})(20\d{2})(?:[^0-9]|$)', fname)
    if p5:
        d_str, m_str, y_str = p5.groups()
        try:
            dt = datetime(int(y_str), int(m_str), int(d_str))
            return dt.strftime("%Y-%m-%d"), dt.strftime("%d %B %Y").upper()
        except ValueError:
            pass

    # Pattern 6: DD-MM-YY or DD_MM_YY or DD.MM.YY (e.g. 08-08-26 -> 2026-08-08)
    p6 = re.search(r'(?:^|[^0-9])(\d{1,2})[-_\.](\d{1,2})[-_\.](\d{2})(?:[^0-9]|$)', fname)
    if p6:
        d_str, m_str, y_short = p6.groups()
        y_str = f"20{y_short}" if len(y_short) == 2 else y_short
        try:
            dt = datetime(int(y_str), int(m_str), int(d_str))
            return dt.strftime("%Y-%m-%d"), dt.strftime("%d %B %Y").upper()
        except ValueError:
            pass

    # Pattern 7: Short date DD-MM or DD_MM or DD.MM (e.g. 08-08, 09-08 -> 2026-08-08, 2026-08-09)
    p7 = re.search(r'(?:^|[^0-9a-zA-Z])(\d{1,2})[-_\.](\d{1,2})(?:[^0-9a-zA-Z]|$)', fname)
    if p7:
        d_str, m_str = p7.groups()
        d_int, m_int = int(d_str), int(m_str)
        if 1 <= d_int <= 31 and 1 <= m_int <= 12:
            try:
                y_val = datetime.now().year if datetime.now().year >= 2026 else 2026
                dt = datetime(y_val, m_int, d_int)
                return dt.strftime("%Y-%m-%d"), dt.strftime("%d %B %Y").upper()
            except ValueError:
                pass

    return None, "DATE UNKNOWN"


KNOWN_NEWSPAPERS = {
    "times of india": "Times of India",
    "toi": "Times of India",
    "bengaluru_hans": "Hans India",
    "hans_india": "Hans India",
    "hans": "Hans India",
    "andhraprabha": "Andhraprabha",
    "andhra prabha": "Andhraprabha",
    "aajtak": "Aajtak",
    "asian age": "Asian Age",
    "aadabhyderabad": "Aadabhyderabad",
    "divya bhaskar": "Divya Bhaskar",
    "divyabhaskar": "Divya Bhaskar",
    "gujarat samachar": "Gujarat Samachar",
    "nava bharat": "Nava Bharat",
    "navabharat": "Nava Bharat",
    "pudhari": "Pudhari",
    "dinakaran": "Dinakaran",
    "mum": "Mumbai News",
    "news hub": "News Hub",
}

def extract_newspaper_info(filename):
    """Extracts normalized newspaper title and ISO date from filename.
    
    Returns tuple: (newspaper_title, iso_date_str)
    Example: ('Times of India', '2026-08-03')
             ('Aadabhyderabad', '2026-08-04')
    """
    if not filename:
        return "UNKNOWN NEWSPAPER", "DATE UNKNOWN"

    iso_date, _ = extract_newspaper_date(filename)
    date_str = iso_date if iso_date else "DATE UNKNOWN"

    from pathlib import Path
    stem = Path(filename).stem.lower()

    for key, norm_name in KNOWN_NEWSPAPERS.items():
        if key in stem:
            return norm_name, date_str

    cleaned = re.sub(r'\d{1,4}[-_\.]\d{1,2}[-_\.]\d{1,4}', ' ', stem)
    cleaned = re.sub(r'\b\d{8}\b', ' ', cleaned)
    cleaned = re.sub(r'(?:^|[-_\s])(copy|tab|tabloid|all pages|all_pages|ap|ts|pdf)(?:$|[-_\s])', ' ', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'[-_\s]+', ' ', cleaned).strip()


    title = cleaned.title() if cleaned else "UNKNOWN NEWSPAPER"
    return title, date_str

