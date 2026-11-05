"""Качване в YouTube от облачна сесия (без браузър на тази машина).

    PY="uv run --quiet --with google-api-python-client --with google-auth python yt_upload.py"
    $PY auth                      # вход в канал: показва код за google.com/device; повтаряш за всеки канал
    $PY channels                  # вързаните канали и дали токенът им е жив
    $PY upload plan.json [--dry-run]
    $PY verify <video_id> [--channel "<канал>"]

Нужно (променливи на средата):
  YT_CLIENT_SECRET_JSON  съдържанието на OAuth клиент от тип "TVs and Limited Input devices" (Google Cloud → Credentials)
                         или YT_CLIENT_SECRET_FILE = пътят до него
  YT_TOKENS_FILE         къде стоят токените (по подразбиране ~/.config/youtube-cloud/tokens.json)

plan.json: [{"channel": "<канал>", "file": "x.mp4", "title": "...", "description": "...", "tags": [...],
             "category": "17", "language": "bg", "privacy": "private",
             "publish_at": "2026-11-06T18:00:00+02:00" | "now" | null, "thumbnail": "t.jpg"}]
publish_at в бъдещето = качва се private и YouTube го пуска сам в този час. "now" = public веднага.
Без publish_at = private (той го пуска сам). При изчерпана квота останалото отива в <plan>.pending.json.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube"]  # позволен за вход с код; покрива качване и тъмбнейл
TOKENS = Path(os.environ.get("YT_TOKENS_FILE", "~/.config/youtube-cloud/tokens.json")).expanduser()
LOG = Path(os.environ.get("YT_UPLOAD_LOG", TOKENS.parent / "uploads.jsonl")).expanduser()


def client():
    raw = os.environ.get("YT_CLIENT_SECRET_JSON")
    if not raw and os.environ.get("YT_CLIENT_SECRET_FILE"):
        raw = Path(os.environ["YT_CLIENT_SECRET_FILE"]).expanduser().read_text()
    if not raw:
        sys.exit("Няма YT_CLIENT_SECRET_JSON (OAuth клиентът от Google Cloud) в средата.")
    c = json.loads(raw)
    c = c.get("installed") or c.get("web") or c
    return c["client_id"], c.get("client_secret", "")


def post(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")


def load_tokens():
    return json.loads(TOKENS.read_text()) if TOKENS.exists() else {}


def save_tokens(t):
    TOKENS.parent.mkdir(parents=True, exist_ok=True)
    tmp = TOKENS.with_suffix(".tmp"); tmp.write_text(json.dumps(t, ensure_ascii=False, indent=1))
    os.chmod(tmp, 0o600); tmp.replace(TOKENS)


def creds(entry):
    from google.oauth2.credentials import Credentials
    cid, secret = client()
    return Credentials(None, refresh_token=entry["refresh_token"], token_uri="https://oauth2.googleapis.com/token",
                       client_id=cid, client_secret=secret, scopes=SCOPES)


def yt(entry):
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=creds(entry), cache_discovery=False)


def cmd_auth():
    cid, secret = client()
    d = post("https://oauth2.googleapis.com/device/code", {"client_id": cid, "scope": " ".join(SCOPES)})
    if "device_code" not in d:
        sys.exit(f"Google отказа входа с код: {d}. Клиентът трябва да е от тип 'TVs and Limited Input devices'.")
    print(f"Отвори {d['verification_url']} и въведи кода: {d['user_code']}  (после избери канала)", flush=True)
    deadline = time.time() + d.get("expires_in", 1800); wait = d.get("interval", 5)
    while time.time() < deadline:
        time.sleep(wait)
        t = post("https://oauth2.googleapis.com/token", {"client_id": cid, "client_secret": secret,
                                                          "device_code": d["device_code"],
                                                          "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        if t.get("error") == "authorization_pending":
            continue
        if t.get("error") == "slow_down":
            wait += 5; continue
        if "refresh_token" not in t:
            sys.exit(f"Входът не мина: {t}")
        entry = {"refresh_token": t["refresh_token"], "added": dt.datetime.now().isoformat(timespec="seconds")}
        ch = yt(entry).channels().list(part="snippet", mine=True).execute()["items"][0]
        entry.update(id=ch["id"], title=ch["snippet"]["title"])
        tokens = load_tokens(); tokens[ch["id"]] = entry; save_tokens(tokens)
        print(f"Вързан: {entry['title']} ({ch['id']})"); return
    sys.exit("Кодът изтече, пусни auth пак.")


def find_channel(name):
    tokens = load_tokens()
    hits = [e for e in tokens.values() if name in (e["id"], e["title"])] or \
           [e for e in tokens.values() if name.lower() in e["title"].lower()]
    if len(hits) != 1:
        sys.exit(f"Канал '{name}': {'няма такъв вързан' if not hits else 'повече от един'}. Вързани: "
                 + ", ".join(e["title"] for e in tokens.values()))
    return hits[0]


def cmd_channels():
    tokens = load_tokens()
    if not tokens:
        print("Няма вързани канали. Пусни: auth"); return
    for e in tokens.values():
        try:
            yt(e).channels().list(part="id", mine=True).execute(); state = "жив"
        except Exception as ex:  # noqa: BLE001
            state = f"МЪРТЪВ ({str(ex)[:80]}): пусни auth за него"
        print(f"{e['title']:30s} {e['id']}  {state}")


def check(item, base):
    errs = []
    f = base / item["file"]
    if not f.exists(): errs.append(f"няма файла {f}")
    if not item.get("title") or len(item["title"]) > 100: errs.append("заглавието е празно или над 100 знака")
    desc = item.get("description", "")
    if len(desc) > 5000: errs.append(f"описанието е {len(desc)} знака (до 5000)")
    if "<" in desc or ">" in desc: errs.append("описанието съдържа < или >")
    if item.get("rules", True):  # правилата на фабриката; "rules": false ги изключва за отделно видео
        sys.path.append(str(Path(__file__).resolve().parent))
        from check_description import check as rules
        short = "#shorts" in desc.lower()
        errs += [f"описание: {e}" for e in rules(desc, short=short) if "5000" not in e and "<" not in e]
    if item.get("thumbnail") and not (base / item["thumbnail"]).exists(): errs.append("няма тъмбнейла")
    pa = item.get("publish_at")
    if pa and pa != "now":
        when = dt.datetime.fromisoformat(pa)
        if when.tzinfo is None: errs.append("publish_at трябва да има часова зона (+02:00)")
        elif when < dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15): errs.append("publish_at е в миналото")
    return errs


def body(item):
    pa = item.get("publish_at")
    status = {"privacyStatus": item.get("privacy", "private"), "selfDeclaredMadeForKids": False}
    if pa == "now":
        status["privacyStatus"] = "public"
    elif pa:
        status["privacyStatus"] = "private"
        status["publishAt"] = dt.datetime.fromisoformat(pa).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    sn = {"title": item["title"], "description": item.get("description", ""), "tags": item.get("tags", []),
          "categoryId": str(item.get("category", "22")),
          "defaultLanguage": item.get("language", "bg"), "defaultAudioLanguage": item.get("language", "bg")}
    return {"snippet": sn, "status": status}


def upload_one(item, base):
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    e = find_channel(item["channel"]); api = yt(e)
    media = MediaFileUpload(str(base / item["file"]), chunksize=16 * 1024 * 1024, resumable=True)
    req = api.videos().insert(part="snippet,status", body=body(item), media_body=media)
    resp, tries = None, 0
    while resp is None:
        try:
            st, resp = req.next_chunk()
            if st: print(f"  {int(st.progress() * 100)}%", flush=True)
        except HttpError as ex:
            if ex.resp.status in (500, 502, 503, 504) and tries < 6:
                tries += 1; time.sleep(2 ** tries); continue
            raise
        except (ConnectionError, TimeoutError, OSError):
            if tries < 6:
                tries += 1; time.sleep(2 ** tries); continue
            raise
    vid = resp["id"]
    if item.get("thumbnail"):
        api.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(base / item["thumbnail"]))).execute()
    rec = {"time": dt.datetime.now().isoformat(timespec="seconds"), "channel": e["title"], "id": vid,
           "url": f"https://youtu.be/{vid}", "title": item["title"], "publish_at": item.get("publish_at"),
           "file": item["file"], "local": item.get("local", [])}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Качено: https://youtu.be/{vid} ({e['title']}, {body(item)['status']})")
    return vid


def cmd_upload(plan_path, dry):
    from googleapiclient.errors import HttpError
    plan_path = Path(plan_path).resolve(); base = plan_path.parent
    items = json.loads(plan_path.read_text())
    bad = {i: check(x, base) for i, x in enumerate(items)}
    for i, errs in bad.items():
        if errs: print(f"[{i}] {items[i].get('title', '?')}: " + "; ".join(errs))
    if any(bad.values()):
        sys.exit("Поправи плана; нищо не е качено.")
    for x in items:
        find_channel(x["channel"])
    if dry:
        for x in items:
            print(json.dumps({"channel": x["channel"], "file": x["file"], **body(x)}, ensure_ascii=False)[:400])
        print("Пробно: всичко е наред, нищо не е качено."); return
    for k, x in enumerate(items):
        try:
            upload_one(x, base)
        except HttpError as ex:
            if "quotaExceeded" in str(ex) or "uploadLimitExceeded" in str(ex):
                rest = plan_path.with_suffix(".pending.json")
                rest.write_text(json.dumps(items[k:], ensure_ascii=False, indent=1))
                sys.exit(f"Квотата за деня свърши. Останалите {len(items) - k} са в {rest}.")
            raise


def cmd_verify(vid, channel=None):
    tokens = load_tokens()
    e = find_channel(channel) if channel else next(iter(tokens.values()))
    r = yt(e).videos().list(part="snippet,status,contentDetails", id=vid).execute()["items"]
    if not r:
        sys.exit("Няма такова видео (или е в друг канал: --channel).")
    v = r[0]
    print(json.dumps({"title": v["snippet"]["title"], "privacy": v["status"]["privacyStatus"],
                      "publishAt": v["status"].get("publishAt"), "description_len": len(v["snippet"]["description"]),
                      "thumb": v["snippet"]["thumbnails"].get("maxres", v["snippet"]["thumbnails"].get("high", {})).get("url"),
                      "duration": v["contentDetails"]["duration"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "auth": cmd_auth()
    elif a[0] == "channels": cmd_channels()
    elif a[0] == "upload": cmd_upload(a[1], "--dry-run" in a)
    elif a[0] == "verify": cmd_verify(a[1], a[a.index("--channel") + 1] if "--channel" in a else None)
    else: sys.exit(__doc__)
