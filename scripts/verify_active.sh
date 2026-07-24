#!/usr/bin/env bash
# verify_active.sh — corre verifies de la feature in_progress (o VERIFY_FEATURE=FN).
# Sin feature activa y sin VERIFY_FEATURE → no-op (exit 0).
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f feature_list.json ]; then
  echo "[verify_active] sin feature_list.json — omitiendo"
  exit 0
fi

if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export VERIFY_FEATURE="${VERIFY_FEATURE:-}"

python3 - <<'PY'
import json
import os
import re
import subprocess
import sys

data = json.load(open("feature_list.json"))
features = data["features"] if isinstance(data, dict) else data
forced = os.environ.get("VERIFY_FEATURE", "").strip().upper()

if forced:
    active = next(
        (f for f in features if str(f.get("id", "")).upper() == forced),
        None,
    )
    if active is None:
        print(f"[verify_active] FAIL: VERIFY_FEATURE={forced} no existe", file=sys.stderr)
        sys.exit(2)
else:
    actives = [f for f in features if f.get("status") == "in_progress"]
    if len(actives) > 1:
        ids = ", ".join(f["id"] for f in actives)
        print(f"[verify_active] FAIL: más de una in_progress: {ids}", file=sys.stderr)
        sys.exit(2)
    if not actives:
        print("[verify_active] ninguna feature in_progress — no-op")
        sys.exit(0)
    active = actives[0]

fid = active["id"]
title = active.get("title", "")
print(f"[verify_active] {fid} — {title}", flush=True)

pattern = re.compile(
    r"(?:\.venv/bin/)?python(?:3)?\s+-m\s+(backend\.scripts\.verify_[\w]+)"
)
cmds: list[str] = []
for step in active.get("verification") or []:
    match = pattern.search(step)
    if match:
        cmd = f"python -m {match.group(1)}"
        if cmd not in cmds:
            cmds.append(cmd)

if not cmds:
    print(
        f"[verify_active] WARN: {fid} sin python -m backend.scripts.verify_* "
        "en verification[] — omitiendo",
        flush=True,
    )
    sys.exit(0)

for cmd in cmds:
    print(f"[verify_active] running: {cmd}", flush=True)
    subprocess.run(cmd, shell=True, check=True)

print("[verify_active] OK", flush=True)
PY
