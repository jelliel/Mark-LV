"""
cx_Freeze setup for THEOLOGICUS
Build: python build_theologicus.py bdist_msi
"""
import sys
from pathlib import Path
from cx_Freeze import setup, Executable

# Project root
base = Path(__file__).parent.resolve()

# Dependencies to include
include_files = [
    (base / "ui_new.html", "ui_new.html"),
    (base / "actions", "actions"),
    (base / "config", "config"),
    (base / "core", "core"),
    (base / "dashboard", "dashboard"),
    (base / "memory", "memory"),
    (base / "research", "research"),
    (base / "readme.md", "readme.md"),
    (base / "requirements.txt", "requirements.txt"),
]

# Build options
build_exe_options = {
    "packages": [
        "PyQt6", "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebChannel",
        "google", "requests", "bs4", "numpy",
        "sounddevice", "numpy", "win32com",
    ],
    "include_files": include_files,
    "excludes": ["tkinter", "unittest", "email", "html", "xml"],
    "optimize": 1,
}

# Build the MSI installer
setup(
    name="THEOLOGICUS",
    version="1.0.8",
    description="THEOLOGICUS - Second Brain for Theological Research",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "main.py",
            base="gui",  # No console window
            icon=str(base / "config" / "jarvis.ico"),
            target_name="THEOLOGICUS.exe",
        )
    ],
)
