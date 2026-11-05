"""Проверява описание по правилата на фабриката, преди да се качи.

    python3 check_description.py описание.txt [--short] [--duration 612]

Дълго видео: без тирета (—, –, --, " - "); глави, първата 0:00, по ред и в рамките на видеото;
редът „Абонирайте се за повече видеа!“; 4–5 хаштага; до 5000 знака; без < и >; без линкове към prirast.io.
Шорт (--short): 2–3 изречения плюс хаштагове, последният е #shorts; без глави.
Изход 0 = наред, 1 = има грешки (изброени).
"""
import re
import sys

SUB_LINE = "Абонирайте се за повече видеа!"
TS = re.compile(r"^\s*((\d{1,2}):)?(\d{1,2}):(\d{2})\s+\S")


def secs(m):
    return int(m.group(2) or 0) * 3600 + int(m.group(3)) * 60 + int(m.group(4))


def check(text, short=False, duration=None):
    errs = []
    if re.search(r"[—–]|--|\s-\s", text):
        errs.append("има тире (—, –, -- или ' - '); правилото е без тирета")
    if len(text) > 5000:
        errs.append(f"{len(text)} знака, а лимитът е 5000")
    if "<" in text or ">" in text:
        errs.append("има < или >, YouTube ги отказва")
    if "prirast.io" in text:
        errs.append("има prirast.io линк, а тук няма връзка с prirast.io")
    tags = re.findall(r"(?<!\w)#[\wА-Яа-я]+", text)
    stamps = [secs(m) for m in (TS.match(l) for l in text.splitlines()) if m]
    if short:
        if stamps:
            errs.append("шортът няма глави")
        if not tags or tags[-1].lower() != "#shorts":
            errs.append("последният хаштаг трябва да е #shorts")
        body = re.sub(r"(?<!\w)#\S+", "", text).strip()
        n = len([s for s in re.split(r"(?<=[.!?…])\s+", body) if s.strip()])
        if not 2 <= n <= 3:
            errs.append(f"{n} изречения, а трябва 2–3")
    else:
        if not stamps:
            errs.append("няма глави с времена")
        else:
            if stamps[0] != 0:
                errs.append("първата глава не е 0:00")
            if any(b <= a for a, b in zip(stamps, stamps[1:])):
                errs.append("главите не са по ред")
            if duration and stamps[-1] >= duration:
                errs.append("последната глава е след края на видеото")
            if len(stamps) < 3:
                errs.append("YouTube иска поне 3 глави, за да ги покаже")
        if SUB_LINE not in text:
            errs.append(f"липсва редът „{SUB_LINE}“")
        if not 4 <= len(tags) <= 5:
            errs.append(f"{len(tags)} хаштага, а трябват 4–5")
    return errs


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    text = open(a[0], encoding="utf-8").read()
    dur = float(a[a.index("--duration") + 1]) if "--duration" in a else None
    errs = check(text, "--short" in a, dur)
    for e in errs:
        print("ГРЕШКА:", e)
    print("Наред." if not errs else f"{len(errs)} грешки.")
    sys.exit(1 if errs else 0)
