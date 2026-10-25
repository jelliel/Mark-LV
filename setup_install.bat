@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   THEOLOGICUS v1.0.5 Installer
echo ========================================
echo.

set INSTALL_DIR=C:\Program Files\Theologicus
set SOURCE_DIR=%~dp0

REM Create install directory
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if errorlevel 1 (
    echo [ERROR] Need administrator privileges to install to Program Files
    echo.
    echo Please run this installer as Administrator, or choose custom location.
    pause
    exit /b 1
)

echo Installing to %INSTALL_DIR%...

REM Copy files
xcopy /E /I /Y "%SOURCE_DIR%actions" "%INSTALL_DIR%\actions"
xcopy /E /I /Y "%SOURCE_DIR%config" "%INSTALL_DIR%\config"
xcopy /E /I /Y "%SOURCE_DIR%core" "%INSTALL_DIR%\core"
xcopy /E /I /Y "%SOURCE_DIR%dashboard" "%INSTALL_DIR%\dashboard"
xcopy /E /I /Y "%SOURCE_DIR%memory" "%INSTALL_DIR%\memory"
xcopy /E /I /Y "%SOURCE_DIR%research" "%INSTALL_DIR%\research"
xcopy /Y "%SOURCE_DIR%main.py" "%INSTALL_DIR%\main.py"
xcopy /Y "%SOURCE_DIR%ui.py" "%INSTALL_DIR%\ui.py"
xcopy /Y "%SOURCE_DIR%ui_new.html" "%INSTALL_DIR%\ui_new.html"
xcopy /Y "%SOURCE_DIR%requirements.txt" "%INSTALL_DIR%\requirements.txt"
xcopy /Y "%SOURCE_DIR%readme.md" "%INSTALL_DIR%\readme.md"

if not exist "%INSTALL_DIR%\dist" mkdir "%INSTALL_DIR%\dist"
xcopy /Y "%SOURCE_DIR%dist\THEOLOGICUS.exe" "%INSTALL_DIR%\dist\THEOLOGICUS.exe"

echo.
echo Creating desktop shortcut...
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Theologicus.lnk'); $Shortcut.TargetPath = '%INSTALL_DIR%\dist\THEOLOGICUS.exe'; $Shortcut.WorkingDirectory = '%INSTALL_DIR%'; $Shortcut.Save()"

echo.
echo ========================================
echo   THEOLOGICUS v1.0.5 installed!
echo ========================================
echo.
echo Location: %INSTALL_DIR%
echo Start menu: Desktop shortcut created
echo.
pause
