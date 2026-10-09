"""Builds svali-autism.command: downloads every finished shot into ~/Desktop/аутизъм as 1.png, 2.png, ..."""
import json, os
here = os.path.dirname(os.path.abspath(__file__))
j = json.load(open(os.path.join(here, "jobs.json")))
done = sorted((int(n), v["url"]) for n, v in j.items() if "url" in v)
lines = ['#!/bin/bash', 'DIR="$HOME/Desktop/аутизъм"', 'mkdir -p "$DIR"', 'cd "$DIR" || exit 1']
# Files are numbered 1..N in video order, even if some shots were skipped.
lines += [f'curl -sSfL -o "{i}.png" "{u}" && echo "{i}.png" || echo "ГРЕШКА при {i}.png"' for i, (_, u) in enumerate(done, 1)]
lines.append('echo "Готово: $DIR"')
out = os.path.join(here, "svali-autism.command")
open(out, "w").write("\n".join(lines) + "\n"); os.chmod(out, 0o755)
print(len(done), "images ->", out)
