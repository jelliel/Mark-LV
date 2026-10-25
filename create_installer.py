# -*- coding: utf-8 -*-
"""THEOLOGICUS installer - creates Windows installer package"""
import os
import sys
import shutil
import subprocess
import zipfile
from pathlib import Path

def main():
    repo = Path(__file__).resolve().parent
    dist_dir = repo / "dist"
    
    # Create installer package
    package_dir = repo / "installer_package"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir()
    
    # Copy all needed files
    for item in repo.iterdir():
        if item.name in ("dist", "installer_package", "build", ".git", "__pycache__", ".venv"):
            continue
        if item.is_file() and item.suffix in ('.py', '.html', '.txt', '.md', '.bat', '.cfg', '.spec'):
            shutil.copy2(item, package_dir / item.name)
        elif item.is_dir():
            shutil.copytree(item, package_dir / item.name, 
                          ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
    
    # Copy EXE
    exe = dist_dir / "THEOLOGICUS.exe"
    if exe.exists():
        shutil.copy2(exe, package_dir / "THEOLOGICUS.exe")
    
    # Create ZIP package
    package_zip = repo / "THEOLOGICUS-v1.0.5-Package.zip"
    with zipfile.ZipFile(package_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(package_dir)
                zf.write(file_path, arcname)
    
    # Cleanup
    shutil.rmtree(package_dir)
    
    print(f"Package created: {package_zip}")
    print(f"Size: {package_zip.stat().st_size / 1024 / 1024:.1f} MB")

if __name__ == "__main__":
    main()
