"""Шортове 9:16 от готовото дълго видео, без CapCut (рецептата от shorts-from-long-video).

    uv run --with pillow --with numpy python render_short.py shorts.json [--only "шорт 2"]

shorts.json:
{
  "src": "Дългото видео.mp4",
  "shorts": [{
    "name": "шорт 1", "out": "шорт 1.mp4",
    "start": 72.8, "end": 131.0,                 # грубо; режи се в най-тихото място наблизо
    "title": "ЗАЩО ИМА\n\nДВА ЦСКА?",           # празен ред между редовете, както го иска
    "words": [["Литекс", 73.1, 73.6], ...]       # думите с времената им в дългото видео (правописът от скрипта)
  }]
}
Вид: бял фон 1080x1920, дългото видео в средата x1.25 по ширина; заглавие в червена (#d7141a) заоблена кутия
горе от 0 до половината (Slide Down / Fade Out); „АБОНИРАЙ СЕ / ЗА КАНАЛА“ последните 4 s; субтитри на един ред,
ГЛАВНИ, Montserrat Black, бели с черен контур, под видеото, без пунктуация, непрекъснати.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE))
from fonts import find_font, title_font  # noqa: E402

W, H, FPS = 1080, 1920, 30
VIDEO_SCALE = 1.25
RED = "#d7141a"
TITLE_Y = round(H / 2 - 0.66 * H / 2)      # центърът на заглавието (y 0.66 в CapCut)
CAP_Y = round(H / 2 + 0.424 * H / 2)       # центърът на субтитрите (y -0.424)
CAP_PX, CAP_MAX = 86, 0.72 * W             # PIL 900 при 100 px = 72% от кадъра, значи ~86 px на екрана
SUB_TEXT, SUB_LEN = "АБОНИРАЙ СЕ\n\nЗА КАНАЛА", 4.0
SLIDE, FADE = 0.35, 0.4

clean = lambda t: re.sub(r"[.,!?:;„“\"…«»()]+(?=\s|$)|^[„“\"«(]+|[„“\"«»]", "", t).strip()


def run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode:
        sys.exit(f"ffmpeg се провали:\n{r.stderr.decode(errors='replace')[-2000:]}")
    return r.stdout


def duration(f):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)]).decode())


def text_box_png(text, out, max_w=880):
    """Бял текст в червена заоблена кутия, с прозрачен фон; връща размера."""
    fp = title_font(); size = 84
    lines = text.split("\n")
    while True:
        f = ImageFont.truetype(fp, size)
        widest = max(f.getlength(l) for l in lines if l) if any(lines) else 0
        if widest <= max_w or size <= 40:
            break
        size -= 2
    pad_x, pad_y, gap = round(size * 0.55), round(size * 0.45), round(size * 0.18)
    asc, desc = f.getmetrics(); lh = asc + desc
    tw = round(widest) + 2 * pad_x
    th = sum((lh if l else round(lh * 0.45)) for l in lines) + gap * (len(lines) - 1) + 2 * pad_y
    im = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, tw - 1, th - 1), radius=round(size * 0.35), fill=RED)
    y = pad_y
    for l in lines:
        if l:
            d.text((tw / 2, y), l, font=f, fill="white", anchor="ma")
            y += lh + gap
        else:
            y += round(lh * 0.45) + gap
    im.save(out)
    return im.size


def quiet_snap(x, sr, t, lo, hi):
    """Най-тихите 20 ms между lo и hi, на кадър (1/30 s)."""
    best, bt = None, t
    for k in range(int(lo * FPS), int(hi * FPS) + 1):
        u = k / FPS
        a, b = int((u - 0.01) * sr), int((u + 0.01) * sr)
        if a < 0 or b > len(x):
            continue
        e = float(np.sqrt(np.mean(x[a:b] ** 2)))
        if best is None or e < best - 1e-9 or (abs(e - best) < 1e-9 and abs(u - t) < abs(bt - t)):
            best, bt = e, u
    return bt


def chunks(words):
    """Думи -> редове от 1-3 думи, ширината мерена с истинския шрифт."""
    f = ImageFont.truetype(find_font("Montserrat-Black.ttf"), CAP_PX)
    out, cur = [], []
    for w, s, e in words:
        w = clean(w).upper()
        if not w:
            continue
        trial = " ".join([c[0] for c in cur] + [w])
        if cur and f.getlength(trial) > CAP_MAX:
            out.append(cur); cur = []
        cur.append((w, s, e))
    if cur:
        out.append(cur)
    return out, f


def ass_time(t):
    t = max(0.0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_ass(groups, f, a, length, out):
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Cap,Montserrat Black,{CAP_PX},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,5,0,5,0,0,0,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    ev = []
    for i, g in enumerate(groups):
        s = g[0][1] - a
        e = (groups[i + 1][0][1] - a) if i + 1 < len(groups) else min(length, g[-1][2] - a + 0.4)
        txt = " ".join(w for w, _, _ in g)
        fs = ""
        if f.getlength(txt) > 0.88 * W:  # една много дълга дума: по-малък шрифт само на този ред
            fs = f"\\fs{int(CAP_PX * 0.88 * W / f.getlength(txt))}"
        ev.append(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},Cap,,0,0,0,,{{\\an5\\pos(540,{CAP_Y}){fs}}}{txt}")
    Path(out).write_text(head + "\n".join(ev) + "\n", encoding="utf-8")
    return len(ev)


def build(src, sh, x, sr, td, base):
    words = [w for w in sh["words"] if sh["start"] - 1 <= w[1] <= sh["end"] + 1]
    if not words:
        sys.exit(f"{sh['name']}: няма думи в този откъс")
    a = quiet_snap(x, sr, sh["start"], words[0][1] - 0.6, words[0][1] - 0.03)
    b = quiet_snap(x, sr, sh["end"], words[-1][2] + 0.03, words[-1][2] + 0.6)
    L = b - a
    groups, f = chunks(words)
    ass = td / f"{sh['name']}.ass"; n = write_ass(groups, f, a, L, ass)
    tpng, spng = td / "title.png", td / "sub.png"
    tw, th = text_box_png(sh["title"], tpng)
    sw, shh = text_box_png(SUB_TEXT, spng)
    T, S = L / 2, max(0.0, L - SUB_LEN)
    vw = round(W * VIDEO_SCALE / 2) * 2
    ty, sy = TITLE_Y - th // 2, TITLE_Y - shh // 2
    fontsdir = str(Path(find_font("Montserrat-Black.ttf")).parent).replace(":", r"\:")
    fc = (f"color=white:s={W}x{H}:r={FPS}:d={L:.6f}[bg];"
          f"[0:v]trim=start={a:.6f}:end={b:.6f},setpts=PTS-STARTPTS,fps={FPS},scale={vw}:-2,setsar=1[v];"
          f"[bg][v]overlay=x=(W-w)/2:y=(H-h)/2:eof_action=pass[b0];"
          f"[1:v]trim=duration={T:.6f},format=rgba,fade=t=in:st=0:d={SLIDE}:alpha=1,"
          f"fade=t=out:st={max(0, T - FADE):.6f}:d={FADE}:alpha=1[t];"
          f"[b0][t]overlay=x=(W-w)/2:y='{ty}-90*max(0\\,1-t/{SLIDE})':enable='between(t,0,{T:.6f})'[b1];"
          f"[2:v]trim=duration={L - S:.6f},format=rgba,fade=t=in:st=0:d={SLIDE}:alpha=1,setpts=PTS-STARTPTS+{S:.6f}/TB[s];"
          f"[b1][s]overlay=x=(W-w)/2:y='{sy}-90*max(0\\,1-(t-{S:.6f})/{SLIDE})':enable='between(t,{S:.6f},{L:.6f})'[b2];"
          f"[b2]ass='{str(ass)}':fontsdir='{fontsdir}',format=yuv420p[out];"
          f"[0:a]atrim=start={a:.6f}:end={b:.6f},asetpts=PTS-STARTPTS[aout]")
    out = (base / sh.get("out", sh["name"] + ".mp4")).resolve()
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-loop", "1", "-framerate", str(FPS), "-i", str(tpng),
         "-loop", "1", "-framerate", str(FPS), "-i", str(spng), "-filter_complex", fc, "-map", "[out]", "-map", "[aout]",
         "-t", f"{L:.6f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)])
    # проверка на субтитрите: светкавици от 1 кадър и залепнали над 2 s
    starts = [g[0][1] - a for g in groups]
    lens = [(starts[i + 1] if i + 1 < len(starts) else L) - starts[i] for i in range(len(starts))]
    flash = sum(1 for d in lens if d <= 1.5 / FPS)
    stuck = [" ".join(w for w, _, _ in groups[i]) for i, d in enumerate(lens[:-1]) if d > 2.0]
    print(f"{sh['name']}: {out.name} {L:.2f} s (рязане {a:.3f}-{b:.3f}), субтитри {n}, "
          f"светкавици {flash}, залепнали >2 s: {stuck[:5] or 'няма'}")


def main():
    plan_path = Path(sys.argv[1]).resolve(); base = plan_path.parent
    P = json.loads(plan_path.read_text())
    src = (base / P["src"]).resolve()
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
    sr = 16000
    x = np.frombuffer(run(["ffmpeg", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]),
                      dtype=np.int16).astype(np.float32) / 32768
    with tempfile.TemporaryDirectory() as td:
        for sh in P["shorts"]:
            if only and sh["name"] not in only:
                continue
            build(src, sh, x, sr, Path(td), base)


if __name__ == "__main__":
    main()
