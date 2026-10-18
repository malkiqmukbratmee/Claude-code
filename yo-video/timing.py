"""Start/end time for every YO image, from the per-sentence timestamps in subs.txt.

Each anchor phrase is located in the transcript (in video order). Its time is interpolated
inside its sentence. Images of one anchor share the time until the next anchor, each at most MAX_LEN s.
"""
import os, re
from scenes import SECTIONS

MAX_LEN = 5.0
HERE = os.path.dirname(os.path.abspath(__file__))
norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[^\w ]", " ", s.lower())).strip()
fmt = lambda x: f"{int(round(x))//60}:{int(round(x))%60:02d}"

def load_subs():
    lines = []
    for raw in open(os.path.join(HERE, "subs.txt"), encoding="utf-8"):
        m = re.match(r"(\d+):(\d+)\s+(.*)", raw.strip())
        if m:
            lines.append((int(m[1]) * 60 + int(m[2]), norm(m[3])))
    text, times = "", []          # times[i] = second at character i of text
    for (t0, s), (t1, _) in zip(lines, lines[1:]):
        s += " "
        times += [t0 + (t1 - t0) * k / len(s) for k in range(len(s))]
        text += s
    return text, times, lines[-1][0]

def rows():
    text, times, end = load_subs()
    cur, marks = 0, []
    for title, _, items in SECTIONS:
        for anchor, scenes in items:
            a = norm(anchor)
            for key, shift in ((a, 0), (a[:25], 0), (a[-25:], len(a) - 25)):
                p = text.find(key, cur)
                if p >= 0:
                    p = max(cur, p - shift); break
            else:
                raise ValueError(anchor)
            cur = p
            marks.append((title, anchor, scenes, times[p]))
    n = 0
    for i, (title, anchor, scenes, t) in enumerate(marks):
        nxt = marks[i + 1][3] if i + 1 < len(marks) else end
        slot = (nxt - t) / len(scenes)
        for k, scene in enumerate(scenes):
            n += 1
            b = t + k * slot
            yield n, title, anchor, scene, b, b + max(1.0, min(slot, MAX_LEN))

if __name__ == "__main__":
    out = ["# ЙО – коя снимка кога влиза (по субтитрите)", "",
           "Снимките са в Desktop/йо като 1.png … 170.png. Времената са по таймлайна в CapCut.", ""]
    sec = None
    for n, title, anchor, scene, b, e in rows():
        if title != sec:
            sec = title
            out += ["", f"## {title}", "", "| Снимка | От | До | Изречение |", "|---|---|---|---|"]
        out.append(f"| **{n}** | {fmt(b)} | {fmt(e)} | „{anchor}“ |")
    open(os.path.join(HERE, "snimki-vreme.md"), "w").write("\n".join(out) + "\n")
    print("\n".join(f"{n}  {fmt(b)} - {fmt(e)}" for n, _, _, _, b, e in rows()))
