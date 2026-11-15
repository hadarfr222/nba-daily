"""Hebrew names for all 30 NBA teams, keyed by ESPN abbreviation."""

# abbreviation: (full Hebrew name, short Hebrew nickname)
TEAMS = {
    "ATL": ("אטלנטה הוקס", "הוקס"),
    "BOS": ("בוסטון סלטיקס", "סלטיקס"),
    "BKN": ("ברוקלין נטס", "נטס"),
    "CHA": ("שארלוט הורנטס", "הורנטס"),
    "CHI": ("שיקגו בולס", "בולס"),
    "CLE": ("קליבלנד קאבלירס", "קאבלירס"),
    "DAL": ("דאלאס מאבריקס", "מאבריקס"),
    "DEN": ("דנוור נאגטס", "נאגטס"),
    "DET": ("דטרויט פיסטונס", "פיסטונס"),
    "GS": ("גולדן סטייט ווריורס", "ווריורס"),
    "HOU": ("יוסטון רוקטס", "רוקטס"),
    "IND": ("אינדיאנה פייסרס", "פייסרס"),
    "LAC": ("לוס אנג'לס קליפרס", "קליפרס"),
    "LAL": ("לוס אנג'לס לייקרס", "לייקרס"),
    "MEM": ("ממפיס גריזליס", "גריזליס"),
    "MIA": ("מיאמי היט", "היט"),
    "MIL": ("מילווקי באקס", "באקס"),
    "MIN": ("מינסוטה טימברוולבס", "טימברוולבס"),
    "NO": ("ניו אורלינס פליקנס", "פליקנס"),
    "NY": ("ניו יורק ניקס", "ניקס"),
    "OKC": ("אוקלהומה סיטי ת'אנדר", "ת'אנדר"),
    "ORL": ("אורלנדו מג'יק", "מג'יק"),
    "PHI": ("פילדלפיה 76'רס", "76'רס"),
    "PHX": ("פיניקס סאנס", "סאנס"),
    "POR": ("פורטלנד טרייל בלייזרס", "בלייזרס"),
    "SAC": ("סקרמנטו קינגס", "קינגס"),
    "SA": ("סן אנטוניו ספרס", "ספרס"),
    "TOR": ("טורונטו ראפטורס", "ראפטורס"),
    "UTAH": ("יוטה ג'אז", "ג'אז"),
    "WSH": ("וושינגטון וויזארדס", "וויזארדס"),
}

# Some sources use other abbreviations for the same team.
ALIASES = {"GSW": "GS", "NOP": "NO", "NYK": "NY", "SAS": "SA", "UTA": "UTAH",
           "WAS": "WSH", "BRK": "BKN", "PHO": "PHX", "CHO": "CHA"}


def _key(abbr: str) -> str:
    abbr = (abbr or "").upper()
    return ALIASES.get(abbr, abbr)


def full_name(abbr: str, fallback: str = "") -> str:
    return TEAMS.get(_key(abbr), (fallback or abbr, ""))[0]


def short_name(abbr: str, fallback: str = "") -> str:
    return TEAMS.get(_key(abbr), ("", fallback or abbr))[1]
