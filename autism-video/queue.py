"""Tracks Higgsfield generation jobs for the shot list in scenes.py.

usage:
  python3 queue.py next K          print JSON requests for the next K shots with no job yet
  python3 queue.py rec N=JOB ...   record submitted job ids
  python3 queue.py done N=URL ...  record completed results
  python3 queue.py drop N ...      forget a failed job so it is resubmitted
  python3 queue.py status          counts
"""
import json, os, sys
from scenes import shots

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.json")

def load():
    return json.load(open(STATE)) if os.path.exists(STATE) else {}

def save(j):
    json.dump(j, open(STATE, "w"), indent=0, sort_keys=True)

cmd, args = sys.argv[1], sys.argv[2:]
j = load()
if cmd == "next":
    k = int(args[0]); out = []
    for n, _, _, _, prompt, ref in shots():
        if str(n) not in j:
            out.append({"index": n, "params": {"model": "gpt_image_2_5", "aspect_ratio": "16:9", "quality": "medium",
                        "resolution": "2k", "prompt": prompt, "medias": [{"role": "image_references", "value": ref}]}})
            if len(out) == k: break
    print(json.dumps(out, ensure_ascii=False))
elif cmd == "rec":
    for a in args:
        n, job = a.split("=", 1); j[n] = {"job": job}
    save(j)
elif cmd == "done":
    for a in args:
        n, url = a.split("=", 1); j[n]["url"] = url
    save(j)
elif cmd == "drop":
    for n in args: j.pop(n, None)
    save(j)
elif cmd == "status":
    total = sum(1 for _ in shots())
    print(f"total={total} submitted={len(j)} done={sum('url' in v for v in j.values())}")
    print("pending_jobs:", json.dumps([{"index": int(n), "job_id": v["job"]} for n, v in sorted(j.items(), key=lambda x: int(x[0])) if "url" not in v]))
