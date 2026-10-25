#!/usr/bin/env python3
"""THEOLOGICUS - bump version and push to jelliel remote with tag"""
import re, sys, subprocess
from pathlib import Path

repo = Path(__file__).resolve().parent
ui_py = repo / "ui.py"
content = ui_py.read_text(encoding="utf-8")

m = re.search(r'THEOLOGICUS\s+v(\d+\.\d+\.\d+)', content)
if not m:
    print("ERROR: No version found in ui.py"); sys.exit(1)

current = m.group(1)
parts = current.split(".")
new = f"{parts[0]}.{parts[1]}.{int(parts[2])+1}"

# Update version
content = re.sub(rf'THEOLOGICUS\s+v{re.escape(current)}', f'THEOLOGICUS v{new}', content)
ui_py.write_text(content, encoding="utf-8")

print(f"Version: {current} -> {new}")

# Git operations
cmds = [
    ["git", "add", "ui.py"],
    ["git", "commit", "-m", f"Bump version to THEOLOGICUS v{new}"],
    ["git", "push", "jelliel", "HEAD"],
    ["git", "tag", "-d", f"v{current}"],
    ["git", "push", "jelliel", f":refs/tags/v{current}"],
    ["git", "tag", "-a", f"v{new}", "-m", f"Theologicus v{new}"],
    ["git", "push", "jelliel", f"v{new}"],
]

for cmd in cmds:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and 'Already up-to-date' not in result.stdout and 'nothing to commit' not in result.stdout.lower():
        print(f"ERROR in {' '.join(cmd)}:")
        print(result.stderr)
        sys.exit(1)

print(f"SUCCESS: Pushed THEOLOGICUS v{new} to jelliel/Mark-LV")
