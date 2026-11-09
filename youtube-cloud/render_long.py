"""Дългото видео без CapCut: снимки на бял фон + войс + бутон „абонирай се“, само с ffmpeg.

    uv run --with pillow python render_long.py plan.json

plan.json:
{
  "voice": "cut.wav",                 # изрязаният войс (той определя дължината)
  "out": "video.mp4",
  "size": [1920, 1080], "fps": 30,
  "photo_scale": 0.8,                 # като в CapCut: вписана в кадъра и после x0.8, белият фон се вижда
  "photos": [{"start": 0.0, "end": 2.9, "file": "a.jpg"}, ...],
  "cards":  [{"start": 30.1, "end": 31.6, "text": "2. Заглавие"} | {"start":..,"end":..,"file":"card.png"}],
  "subscribe": [{"start": 61.2, "end": 66.0}],          # бутонът е без звук, само на бял екран (снимките под него се махат)
  "subscribe_clip": "subscribe-keyed.mov",              # с алфа; или зеленият оригинал + "subscribe_green": true
}
Празното между снимките остава бял фон. Времената се закръглят към кадър (1/fps).
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE))
from fonts import find_font  # noqa: E402

GREEN = "0x63E304"  # зеленото на клипа с бутона (RGB 99,227,4)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg се провали:\n{' '.join(map(str, cmd))[:600]}\n{r.stderr[-2000:]}")
    return r.stdout


def duration(f):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)]).strip())


def photo_frame(src, W, H, scale, out):
    im = ImageOps.exif_transpose(Image.open(src))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, "white"); bg.alpha_composite(im); im = bg
    im = im.convert("RGB")
    k = min(W / im.width, H / im.height) * scale
    im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), "white")
    canvas.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    canvas.save(out, quality=95)


def card_frame(text, W, H, out):
    canvas = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(canvas)
    font_path = find_font("Montserrat-Black.ttf")
    size = 120
    while size > 30:
        f = ImageFont.truetype(font_path, size)
        box = d.multiline_textbbox((0, 0), text, font=f, align="center", spacing=size // 4)
        if box[2] - box[0] <= W * 0.85 and box[3] - box[1] <= H * 0.6:
            break
        size -= 4
    d.multiline_text((W / 2, H / 2), text, font=f, fill="black", anchor="mm", align="center", spacing=size // 4)
    canvas.save(out, quality=95)


def main():
    plan_path = Path(sys.argv[1]).resolve()
    P = json.loads(plan_path.read_text())
    base = plan_path.parent
    rel = lambda p: (base / p).resolve()
    W, H = P.get("size", [1920, 1080]); fps = P.get("fps", 30); scale = P.get("photo_scale", 0.8)
    voice = rel(P["voice"]); total = duration(voice)
    fr = lambda t: round(t * fps) / fps  # към кадър

    items = []
    for x in P.get("photos", []):
        items.append(("photo", fr(x["start"]), fr(x["end"]), x["file"]))
    for x in P.get("cards", []):
        items.append(("card", fr(x["start"]), fr(x["end"]), x.get("file") or x["text"]))
    items = sorted((i for i in items if i[2] > i[1]), key=lambda i: i[1])
    for a, b in zip(items, items[1:]):
        if b[1] < a[2] - 1e-6:
            sys.exit(f"Застъпване: {a[3]} до {a[2]:.3f} s и {b[3]} от {b[1]:.3f} s")
    missing = [i[3] for i in items if i[0] == "photo" and not rel(i[3]).exists()]
    if missing:
        sys.exit("Липсват снимки: " + ", ".join(missing[:10]))

    # „Абонирай се“ стои само на бял екран: докато върви бутонът, снимките и картите се махат.
    subs = [(fr(s["start"]), fr(s["end"])) for s in P.get("subscribe", [])]
    clip = rel(P["subscribe_clip"]) if P.get("subscribe_clip") else None
    if subs and (not clip or not clip.exists()):
        sys.exit("Има места за „абонирай се“, но няма subscribe_clip (клипът с бутона).")
    clip_len = duration(clip) if subs else 0.0
    spans = [(a, a + min(b - a, clip_len - 1 / fps)) for a, b in subs]
    for sa, sb in spans:
        cut = []
        for kind, a, b, what in items:
            if b <= sa or a >= sb:
                cut.append((kind, a, b, what)); continue
            if a < sa:
                cut.append((kind, a, sa, what))
            if b > sb:
                cut.append((kind, sb, b, what))
        items = [i for i in cut if i[2] - i[1] > 0.5 / fps]

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        white = td / "white.jpg"; Image.new("RGB", (W, H), "white").save(white, quality=95)
        lines, t = [], 0.0

        def add(frame, dur):
            lines.append(f"file '{frame}'\nduration {dur:.6f}\n")

        for n, (kind, a, b, what) in enumerate(items):
            if a > t + 1e-6:
                add(white, a - t)
            f = td / f"{n:04d}.jpg"
            if kind == "photo":
                photo_frame(rel(what), W, H, scale, f)
            elif Path(str(what)).suffix.lower() in (".png", ".jpg", ".jpeg") and rel(what).exists():
                photo_frame(rel(what), W, H, 1.0, f)
            else:
                card_frame(what, W, H, f)
            add(f, b - a); t = b
        end = fr(total)
        if end > t + 1e-6:
            add(white, end - t)
        last = lines[-1].split("\n")[0]
        (td / "list.txt").write_text("".join(lines) + last + "\n")  # concat иска последния кадър пак

        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(td / "list.txt"), "-i", str(voice)]
        fc = f"[0:v]fps={fps},format=yuv420p,setsar=1[base]"
        cur = "base"
        if subs:
            for k, (a, b) in enumerate(spans):
                cmd += ["-i", str(clip)]
                key = (f"chromakey={GREEN}:0.10:0.06,despill=type=green:mix=0.6," if P.get("subscribe_green") else "")
                dur = b - a
                fc += (f";[{k + 2}:v]{key}scale={W}:{H},fps={fps},trim=0:{dur:.6f},format=yuva420p,"
                       f"setpts=PTS-STARTPTS+{a:.6f}/TB[s{k}]"
                       f";[{cur}][s{k}]overlay=eof_action=pass:enable='between(t,{a:.6f},{a + dur:.6f})'[v{k}]")
                cur = f"v{k}"
        cmd += ["-filter_complex", fc, "-map", f"[{cur}]", "-map", "1:a", "-t", f"{end:.6f}",
                "-c:v", "libx264", "-preset", os.environ.get("X264_PRESET", "medium"), "-crf", "18",
                "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-movflags", "+faststart", str(rel(P.get("out", "video.mp4")))]
        run(cmd)
    out = rel(P.get("out", "video.mp4"))
    print(f"Готово: {out} ({duration(out):.2f} s, войс {total:.2f} s, снимки {sum(1 for i in items if i[0]=='photo')}, "
          f"карти {sum(1 for i in items if i[0]=='card')}, абонирай се {len(subs)})")


if __name__ == "__main__":
    main()
