"""Non-AI check: a weekday that doesn't match its date ('Monday, 27 Oct 2026' when it was a Tuesday).

Forged receipts often get this wrong because the forger edits the date but not the weekday.
"""

import re
from datetime import date

WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

_WD = r"(mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?"
_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
PATTERNS = [
    # Tuesday, 27 Oct 2026
    re.compile(rf"\b{_WD}\s+(\d{{1,2}})(?:st|nd|rd|th)?\s+{_MON},?\s+(\d{{4}})", re.I),
    # Tuesday, October 27, 2026
    re.compile(rf"\b{_WD}\s+{_MON}\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})", re.I),
    # Tue 27/10/2026 (day/month/year)
    re.compile(rf"\b{_WD}\s+(\d{{1,2}})[/.-](\d{{1,2}})[/.-](\d{{4}})", re.I),
]


def weekday_mismatches(text: str) -> list[str]:
    found = []
    for i, pat in enumerate(PATTERNS):
        for m in pat.finditer(text or ""):
            g = m.groups()
            try:
                if i == 0:
                    wd, d, mon, y = g[0], int(g[1]), MONTHS[g[2][:3].lower()], int(g[3])
                elif i == 1:
                    wd, mon, d, y = g[0], MONTHS[g[1][:3].lower()], int(g[2]), int(g[3])
                else:
                    wd, d, mon, y = g[0], int(g[1]), int(g[2]), int(g[3])
                real = date(y, mon, d).weekday()
            except (ValueError, KeyError):
                continue
            if real != WEEKDAYS[wd[:3].lower()]:
                found.append(f'The date "{m.group(0).strip()}" is wrong: {date(y, mon, d):%d %b %Y} was a '
                             f"{DAY_NAMES[real]}. Edited receipts often get this wrong.")
    return list(dict.fromkeys(found))
