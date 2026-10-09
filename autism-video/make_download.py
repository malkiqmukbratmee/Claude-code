"""Builds svali-autism.command: downloads every finished shot into ~/Desktop/аутизъм as 1.png, 2.png, ..."""
import json, os
here = os.path.dirname(os.path.abspath(__file__))
j = json.load(open(os.path.join(here, "jobs.json")))
done = sorted((int(n), v["url"]) for n, v in j.items() if "url" in v)
lines = ['#!/bin/bash', 'DIR="$HOME/Desktop/аутизъм"', 'mkdir -p "$DIR"', 'cd "$DIR" || exit 1']
lines += [f'curl -sSfL -o "{n}.png" "{u}" && echo "{n}.png" || echo "ГРЕШКА при {n}.png"' for n, u in done]
lines.append('echo "Готово: $DIR"')
out = os.path.join(here, "svali-autism.command")
open(out, "w").write("\n".join(lines) + "\n"); os.chmod(out, 0o755)
print(len(done), "images ->", out)
