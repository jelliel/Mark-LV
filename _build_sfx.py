"""Build THEOLOGICUS SFX installer using 7-Zip"""
import subprocess, os, shutil, zipfile
from pathlib import Path

repo = Path('.').resolve()
out_exe = repo / 'THEOLOGICUS-v1.0.8-Setup.exe'
sfx_module = r'C:\Program Files\7-Zip\7z.sfx'
pkg_dir = repo / '_installer_pkg'
zip_path = repo / '_temp_installer.zip'

for p in [out_exe, pkg_dir / 'config.cfg', zip_path]:
    if p.exists(): p.unlink(missing_ok=True)
if pkg_dir.exists(): shutil.rmtree(pkg_dir)
pkg_dir.mkdir()

skip = {'dist','build','.git','__pycache__','_installer_pkg','.claude','.venv','node_modules'}
for item in sorted(repo.iterdir()):
    if item.name in skip: continue
    if item.is_file():
        shutil.copy2(item, pkg_dir / item.name)
    elif item.is_dir():
        d = pkg_dir / item.name
        if not d.exists():
            shutil.copytree(item, d, ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git'))

cfg = pkg_dir / 'config.cfg'
cfg.write_text(''';!@Install@!UTF-8!
Title="THEOLOGICUS v1.0.8"
BeginPrompt="Theologicus Installation\nInstall to: C:\\Program Files\\Theologicus"
ExtractDialogText="Extracting files..."
ExtractTimeout=600
GUIMode="0"
ExtractToPath="C:\\Program Files\\Theologicus"
OverwriteMode="1"
;!@InstallEnd@!
''', encoding='utf-16le')

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(pkg_dir):
        for f in files:
            fp = Path(root) / f
            zf.write(fp, fp.relative_to(pkg_dir))

print(f"ZIP size: {zip_path.stat().st_size/1024:.1f} KB")

cmd = [r'C:\Program Files\7-Zip\7z.exe', 'a', '-sfx', sfx_module,
       str(out_exe), str(cfg), str(zip_path)]
r = subprocess.run(cmd, capture_output=True, text=True)
print('RC:', r.returncode)
if r.stderr: print('ERR:', r.stderr[-500:])

if out_exe.exists():
    sz = out_exe.stat().st_size / 1024 / 1024
    print(f"SUCCESS: {out_exe} ({sz:.1f} MB)")
else:
    print("FAILED")

for p in [zip_path, cfg]:
    if p.exists(): p.unlink()
if pkg_dir.exists(): shutil.rmtree(pkg_dir)
