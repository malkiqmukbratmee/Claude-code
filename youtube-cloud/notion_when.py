"""Чете датата и часа под „Качване:“ от страница в Notion и ги връща като ISO време (Europe/Sofia).

    python3 notion_when.py "<текстът след Качване:>"      -> 2026-11-06T18:00:00+02:00, изход 0
                                                          -> „НЯМА ДАТА И ЧАС“, изход 1
    python3 notion_when.py --thumb "<текстът след Тъмб:>"  -> „ИМА ТЪМБНЕЙЛ“ (0) / „НЯМА ТЪМБНЕЙЛ“ (1)

ЗАКОН (Георги, 2026-11-09): видео се качва само когато в Notion има И дата и час под „Качване:“, И тъмбнейл под „Тъмб:“.

ПРАВИЛО: без конкретна дата И час нищо не се качва и не се насрочва (нито видеото, нито шортовете).
Шаблонът „Дата и час“, празно, само дата, само час или думи като „утре“ не стигат.
Приема: 6.11.2026 18:00, 06.11 18:00, 6/11/2026 18.30, 2026-11-06 18:00, 6 ноември 2026 18:00, 6 ноември 18ч.
Без година = текущата (или следващата, ако датата вече е минала).
"""
import datetime as dt
import re
import sys
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Sofia")
MONTHS = {"януари": 1, "февруари": 2, "март": 3, "април": 4, "май": 5, "юни": 6, "юли": 7, "август": 8,
          "септември": 9, "октомври": 10, "ноември": 11, "декември": 12}
TIME = r"(?<!\d)(?P<h>[01]?\d|2[0-3])(?:[:.](?P<m>[0-5]\d)(?!\d)|\s*ч)"
SEP = r"\s*(?:г\.?)?(?:\s*,\s*|\s+в\s+|\s+от\s+|\s+)"  # задължителен разделител между дата и час


def parse(text, now=None):
    now = now or dt.datetime.now(TZ)
    t = " ".join((text or "").lower().split())
    if not t or "дата и час" in t:
        return None
    pats = [
        r"(?<!\d)(?P<y>20\d\d)-(?P<mo>\d{1,2})-(?P<d>\d{1,2})(?:t|" + SEP + ")" + TIME,
        r"(?<!\d)(?P<d>\d{1,2})[./](?P<mo>\d{1,2})(?:[./](?P<y>20\d\d|\d\d))?(?![\d./])" + SEP + TIME,
        r"(?<!\d)(?P<d>\d{1,2})\s+(?P<mn>[а-я]+)(?:\s+(?P<y>20\d\d))?" + SEP + TIME,
    ]
    for p in pats:
        m = re.search(p, t)
        if not m:
            continue
        g = m.groupdict()
        mo = MONTHS.get(g.get("mn") or "") if g.get("mn") else int(g["mo"])
        if not mo:
            continue
        y = g.get("y")
        y = int(y) + (2000 if y and len(y) == 2 else 0) if y else now.year
        try:
            when = dt.datetime(y, mo, int(g["d"]), int(g["h"]), int(g.get("m") or 0), tzinfo=TZ)
        except ValueError:
            return None
        if not g.get("y") and when < now - dt.timedelta(days=1):
            when = when.replace(year=when.year + 1)
        return when
    return None


def thumb_ok(text):
    """Има ли тъмбнейл под „Тъмб:“: линк (http...) или прикачен файл в Notion. Празно или шаблон = няма."""
    t = (text or "").strip()
    return bool(re.search(r"https?://\S+|notion-file-block://\S+|attachment:\S+|file://\S+", t))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--thumb"]:
        ok = thumb_ok(" ".join(sys.argv[2:]))
        print("ИМА ТЪМБНЕЙЛ" if ok else "НЯМА ТЪМБНЕЙЛ: не качвам")
        sys.exit(0 if ok else 1)
    w = parse(" ".join(sys.argv[1:]))
    if not w:
        print("НЯМА ДАТА И ЧАС: не качвам и не насрочвам")
        sys.exit(1)
    print(w.isoformat())
