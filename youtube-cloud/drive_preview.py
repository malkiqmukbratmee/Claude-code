"""Готовото видео в Google Drive за преглед: качване и публичен линк („всеки с линка може да гледа“).

    PY="uv run --quiet --with google-api-python-client --with google-auth python drive_preview.py"
    $PY auth                       # еднократно: код за google.com/device, влизаш в акаунта на Drive
    $PY put "<видео>.mp4" [--folder "YouTube преглед"]   # качва, дава публичен линк, печата го

Ползва същия OAuth клиент (YT_CLIENT_SECRET_JSON) и същия файл с токени (YT_TOKENS_FILE), под ключа "_drive".
Обхватът е drive.file: скриптът вижда само файловете, които сам е качил.
"""
import json
import sys
import time

from yt_upload import client, load_tokens, post, save_tokens

SCOPE = "https://www.googleapis.com/auth/drive.file"


def cmd_auth():
    cid, secret = client()
    d = post("https://oauth2.googleapis.com/device/code", {"client_id": cid, "scope": SCOPE})
    if "device_code" not in d:
        sys.exit(f"Google отказа входа с код: {d}")
    print(f"Отвори {d['verification_url']} и въведи кода: {d['user_code']}  (влез в акаунта на Drive)", flush=True)
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
        tokens = load_tokens(); tokens["_drive"] = {"refresh_token": t["refresh_token"], "scope": SCOPE}
        save_tokens(tokens)
        print("Вързан: Google Drive"); return
    sys.exit("Кодът изтече, пусни auth пак.")


def drive():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    e = load_tokens().get("_drive")
    if not e:
        sys.exit("Drive не е вързан. Пусни: drive_preview.py auth")
    cid, secret = client()
    c = Credentials(None, refresh_token=e["refresh_token"], token_uri="https://oauth2.googleapis.com/token",
                    client_id=cid, client_secret=secret, scopes=[SCOPE])
    return build("drive", "v3", credentials=c, cache_discovery=False)


def folder_id(svc, name):
    q = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    got = svc.files().list(q=q, fields="files(id)", spaces="drive").execute().get("files", [])
    if got:
        return got[0]["id"]
    return svc.files().create(body={"name": name, "mimeType": "application/vnd.google-apps.folder"},
                              fields="id").execute()["id"]


def cmd_put(path, folder):
    from googleapiclient.http import MediaFileUpload
    from pathlib import Path
    svc = drive()
    p = Path(path)
    body = {"name": p.name, "parents": [folder_id(svc, folder)]}
    req = svc.files().create(body=body, media_body=MediaFileUpload(str(p), mimetype="video/mp4", resumable=True,
                                                                   chunksize=16 * 1024 * 1024), fields="id")
    res = None
    while res is None:
        st, res = req.next_chunk()
        if st:
            print(f"  {int(st.progress() * 100)}%", flush=True)
    fid = res["id"]
    svc.permissions().create(fileId=fid, body={"type": "anyone", "role": "reader"}).execute()
    link = f"https://drive.google.com/file/d/{fid}/view?usp=sharing"
    print(json.dumps({"id": fid, "link": link}, ensure_ascii=False))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["auth"]:
        cmd_auth()
    elif a[:1] == ["put"] and len(a) >= 2:
        f = a[a.index("--folder") + 1] if "--folder" in a else "YouTube преглед"
        cmd_put(a[1], f)
    else:
        sys.exit(__doc__)
