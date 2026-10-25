@echo off
REM Setup script for PyQt6-WebEngine
echo Checking Python versions and installing PyQt6-WebEngine...

REM Try Python 3.12 first (most likely the one used by the app)
echo Checking Python 3.12...
"C:\Users\toshr\AppData\Local\Programs\Python\Python312\python.exe" -m pip show PyQt6-WebEngine >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo PyQt6-WebEngine already installed for Python 3.12
) else (
    echo Installing PyQt6-WebEngine for Python 3.12...
    "C:\Users\toshr\AppData\Local\Programs\Python\Python312\python.exe" -m pip install PyQt6-WebEngine
)

REM Verify installation
echo.
echo Verifying installation...
"C:\Users\toshr\AppData\Local\Programs\Python\Python312\python.exe" -c "from PyQt6.QtWebEngineWidgets import QWebEngineView; print('SUCCESS: QWebEngineView available')"

echo.
echo Done!
