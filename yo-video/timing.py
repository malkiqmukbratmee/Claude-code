"""Estimates start/end time for every YO image from where its anchor phrase sits in the transcript.

Speech is assumed to be evenly paced inside each transcript section, so times are approximate (about ±2-3 s).
Each image runs at most MAX_LEN seconds, leaving short gaps where the speaker is on screen.
"""
import re
from transcript import SECTIONS as T, END
from scenes import SECTIONS as S

MAX_LEN = 5.0
sec = lambda t: int(t.split(":")[0]) * 60 + int(t.split(":")[1])
norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[^\w ]", " ", s.lower())).strip()
fmt = lambda x: f"{int(x)//60}:{int(x)%60:02d}"

def anchor_pos(text, anchor):
    t, a = norm(text), norm(anchor)
    for key, shift in ((a, 0), (a[:25], 0), (a[-25:], len(a) - 25)):
        p = t.find(key)
        if p >= 0:
            return max(0, p - shift)
    raise ValueError(anchor)

def rows():
    starts = [sec(t) for t, _ in T] + [sec(END)]
    n = 0
    for i, ((_, text), (title, _, items)) in enumerate(zip(T, S)):
        s0, s1, L = starts[i], starts[i + 1], len(norm(text))
        times = [s0 + (s1 - s0) * anchor_pos(text, a) / L for a, _ in items] + [s1]
        for j, (anchor, scenes) in enumerate(items):
            slot = (times[j + 1] - times[j]) / len(scenes)
            for k, scene in enumerate(scenes):
                n += 1
                b = times[j] + k * slot
                yield n, title, anchor, scene, b, b + min(slot, MAX_LEN)

if __name__ == "__main__":
    out = ["# ЙО – коя снимка кога влиза", "",
           "Снимките са в Desktop/йо като 1.png … 170.png. Времената са по таймлайна в CapCut, изчислени по мястото на изречението в текста, затова може да се разминават с 2–3 секунди. Ориентирай се по цитата и дръпни снимката до точната дума.", ""]
    sec_t = None
    for n, title, anchor, scene, b, e in rows():
        if title != sec_t:
            sec_t = title
            out += ["", f"## {title}", "", "| Снимка | От | До | Изречение |", "|---|---|---|---|"]
        out.append(f"| **{n}** | {fmt(b)} | {fmt(e)} | „{anchor}“ |")
    open("snimki-vreme.md", "w").write("\n".join(out) + "\n")
    print("ok")
