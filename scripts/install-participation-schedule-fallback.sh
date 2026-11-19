#!/bin/bash
set -euo pipefail

if [[ $# != 2 || "$1" != /* || "$2" != /* || ! -x "$1" || ! -x "$2" ]]; then
  echo "Usage: bash $0 /absolute/path/to/python3 /absolute/path/to/gh" >&2
  exit 2
fi

label=com.hanshanley.participation-schedule-fallback
domain="gui/$(id -u)"
launchctl print "$domain" >/dev/null
home="$HOME/Library/Application Support/ParticipationScheduleFallback"
plist="$HOME/Library/LaunchAgents/$label.plist"
if [[ -e "$home" || -L "$home" || -e "$plist" || -L "$plist" ]] ||
   launchctl print "$domain/$label" >/dev/null 2>&1; then
  echo "An installation already exists; refusing to replace it" >&2
  exit 1
fi
if [[ "$("$2" api --hostname github.com user --jq .login)" != hanshanley ]]; then
  echo "The existing GitHub CLI login must be hanshanley" >&2
  exit 1
fi

umask 077
mkdir "$home"
mkdir -p "$HOME/Library/LaunchAgents"
source_dir="$(dirname "$0")"
cp "$source_dir/participation-schedule-fallback.py" "$home/fallback.py"
"$1" - "$plist" "$label" "$home" "$1" "$2" <<'PY'
import plistlib
from pathlib import Path
import sys

filename, label, directory, python, gh = sys.argv[1:]
home = Path(directory)
with Path(filename).open("xb") as out:
    plistlib.dump({
        "Label": label,
        "ProgramArguments": [python, str(home / "fallback.py"), "--gh", gh,
                             "--state-dir", str(home), "--apply"],
        "StartInterval": 300,
        "StandardOutPath": str(home / "actions.log"),
        "StandardErrorPath": str(home / "errors.log"),
        "Umask": 0o077,
    }, out)
PY
plutil -lint "$plist"
launchctl bootstrap "$domain" "$plist"
echo "Installed $label; launchd will invoke it at the next interval."
