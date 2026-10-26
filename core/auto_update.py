"""THEOLOGICUS Auto-Update Module
Checks GitHub releases on startup and notifies UI when update is available.
"""
import json
import platform
import subprocess
import threading
import urllib.request
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

APP_VERSION = "1.0.11"
GITHUB_REPO = "jelliel/Theologicus-AI"
APP_NAME = "THEOLOGICUS-AI"


class AutoUpdater(QObject):
    """Background thread that checks for updates and signals UI."""
    update_found = pyqtSignal(object)  # dict with version, name, url, size
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._thread = None

    def start_check(self):
        """Start update check in background thread."""
        self._thread = threading.Thread(
            target=self._check_loop, daemon=True
        )
        self._thread.start()

    def _check_loop(self):
        try:
            info = self._check_for_update()
            if info:
                self.update_found.emit(info)
            else:
                print(f"[AutoUpdate] Current version v{APP_VERSION} is up to date.")
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _check_for_update(self):
        """Fetch latest release and compare versions."""
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={
                "User-Agent": f"THEOLOGICUS-AI/{APP_VERSION}",
                "Accept": "application/vnd.github.v3+json"
            })
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())

            latest_tag = data.get("tag_name", "").lstrip("v")
            current = tuple(int(x) for x in APP_VERSION.split("."))
            latest = tuple(int(x) for x in latest_tag.split("."))

            if latest <= current:
                return None

            # Find Setup.exe asset
            for asset in data.get("assets", []):
                if asset["name"].endswith("-Setup.exe"):
                    return {
                        "version": data["tag_name"],
                        "name": asset["name"],
                        "url": asset["browser_download_url"],
                        "size": asset["size"],
                        "notes": data.get("body", "")
                    }
            return None
        except Exception as e:
            print(f"[AutoUpdate] Check failed: {e}")
            return None

    def download_and_install(self, info, progress_callback=None):
        """Download installer and run it."""
        try:
            temp_dir = Path(__file__).parent.parent / "temp_update"
            temp_dir.mkdir(exist_ok=True)
            safe_name = Path(info["name"]).name  # strip any directory components
            dest = temp_dir / safe_name

            req = urllib.request.Request(info["url"], headers={
                "User-Agent": f"THEOLOGICUS-AI/{APP_VERSION}"
            })
            with urllib.request.urlopen(req, timeout=300) as r:
                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                chunk = 8192
                with open(dest, "wb") as f:
                    while True:
                        data = r.read(chunk)
                        if not data:
                            break
                        f.write(data)
                        downloaded += len(data)
                        if progress_callback and total:
                            progress_callback(downloaded * 100 / total)

            print(f"[AutoUpdate] Running installer: {dest}")
            cmd = [str(dest), "/SILENT", "/NORESTART", "/SUPPRESSMSGBOXES"]
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
            return True
        except Exception as e:
            print(f"[AutoUpdate] Install failed: {e}")
            self.error_occurred.emit(str(e))
            return False


# Alias for backward compatibility
UpdateChecker = AutoUpdater
