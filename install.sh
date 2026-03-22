#!/usr/bin/env bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${HOME}/.newmax/skills/daily-reminder_VPS"
OPENCLAW_JSON="${HOME}/.openclaw/openclaw.json"
CRON_JSON="${HOME}/.openclaw/cron/jobs.json"
STATE_JSON="${HOME}/.openclaw/workspace/.daily-reminder_VPS/state.json"
export OPENCLAW_JSON

echo "Installing daily-reminder_VPS from: ${REPO_DIR}"

mkdir -p "${HOME}/.newmax/skills"
mkdir -p "${HOME}/.openclaw/cron"
mkdir -p "${HOME}/.openclaw/workspace"

if [[ "${REPO_DIR}" != "${TARGET_DIR}" ]]; then
  ln -sfn "${REPO_DIR}" "${TARGET_DIR}"
  echo "Linked skill to ${TARGET_DIR}"
else
  echo "Skill is already located at ${TARGET_DIR}"
fi

python3 - <<'PY'
import json
from datetime import datetime
import os
from pathlib import Path
import shutil

path = Path(os.environ["OPENCLAW_JSON"]).expanduser()
path.parent.mkdir(parents=True, exist_ok=True)

if path.exists():
    current = json.loads(path.read_text())
else:
    current = {}

original = json.dumps(current, ensure_ascii=False, sort_keys=True)
current.setdefault("skills", {})
current["skills"].setdefault("entries", {})
current["skills"]["entries"]["daily-reminder_VPS"] = {"enabled": True}

updated = json.dumps(current, ensure_ascii=False, sort_keys=True)
if path.exists() and updated != original:
    backup = path.with_name(f"{path.name}.{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak")
    shutil.copy2(path, backup)

path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n")
if updated == original:
    print(f"{path} already up to date")
else:
    print(f"Updated {path}")
PY

python3 "${REPO_DIR}/scripts/install_cron.py" --jobs-path "${CRON_JSON}"
python3 "${REPO_DIR}/scripts/daily_reminder_state.py" --state "${STATE_JSON}" ensure-state

echo "Installation finished."
echo "Restart OpenClaw, then send:"
echo "  每日提醒 开始"
