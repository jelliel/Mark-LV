@echo off
rem THEOLOGICUS — lance l'app depuis son propre environnement (venv), pas le Python global.
cd /d "%~dp0"
".venv\Scripts\python.exe" main.py %*
if errorlevel 1 pause
