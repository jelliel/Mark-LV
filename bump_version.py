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

content = re.sub(rf'THEOLOGICUS\s+v{re.escape(current)}', f'THEOLOGICUS-AI v{new}', content)
ui_py.write_text(content, encoding="utf-8")

print(f"Version: {current} -> {new}")

# Git operations
for cmd in [
    ["git", "add", "ui.py"],
    ["git", "commit", "-m", f"Bump version to THEOLOGICUS-AI v{new}"],
    ["git", "push", "jelliel", "HEAD"],
]:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ERROR: {' '.join(cmd)} -> {r.stderr.strip()}"); sys.exit(1)

# Handle tags - delete old, create new, push
subprocess.run(["git", "tag", "-d", f"v{current}"], capture_output=True)
subprocess.run(["git", "push", "jelliel", f":refs/tags/v{current}"], capture_output=True)
subprocess.run(["git", "tag", "-d", f"v{new}"], capture_output=True)
subprocess.run(["git", "push", "jelliel", f":refs/tags/v{new}"], capture_output=True)
subprocess.run(["git", "tag", "-a", f"v{new}", "-m", f"Theologicus v{new}"], check=True)
subprocess.run(["git", "push", "jelliel", f"v{new}"], check=True)

print(f"SUCCESS: THEOLOGICUS-AI v{new} pushed to jelliel/Mark-LV")
