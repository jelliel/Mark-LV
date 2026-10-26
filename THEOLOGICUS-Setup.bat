@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   THEOLOGICUS v1.0.8 - Installation
echo ========================================
echo.

:: Check for admin rights
net session >nul 2>&1
if %errorLevel% equ 0 (
    echo [INFO] Administrator rights detected
    set INSTALL_DIR=C:\Program Files\Theologicus
) else (
    echo [INFO] No admin rights - installing to user directory
    set INSTALL_DIR=%USERPROFILE%\Theologicus
)

:: Create install directory
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
echo [1/4] Installing to: %INSTALL_DIR%

:: Copy files
echo [2/4] Copying files...
xcopy /E /I /Y "%~dp0actions" "%INSTALL_DIR%\actions"
xcopy /E /I /Y "%~dp0config" "%INSTALL_DIR%\config"
xcopy /E /I /Y "%~dp0core" "%INSTALL_DIR%\core"
xcopy /E /I /Y "%~dp0dashboard" "%INSTALL_DIR%\dashboard"
xcopy /E /I /Y "%~dp0memory" "%INSTALL_DIR%\memory"
xcopy /E /I /Y "%~dp0research" "%INSTALL_DIR%\research"
copy /Y "%~dp0main.py" "%INSTALL_DIR%\" >nul
copy /Y "%~dp0ui.py" "%INSTALL_DIR%\" >nul
copy /Y "%~dp0ui_new.html" "%INSTALL_DIR%\" >nul
copy /Y "%~dp0requirements.txt" "%INSTALL_DIR%\" >nul
copy /Y "%~dp0readme.md" "%INSTALL_DIR%\" >nul
copy /Y "%~dp0bump_version.py" "%INSTALL_DIR%\" >nul
copy /Y "%~dp0setup_theologicus.bat" "%INSTALL_DIR%\" >nul

:: Create dist folder and copy EXE
if not exist "%INSTALL_DIR%\dist" mkdir "%INSTALL_DIR%\dist"
copy /Y "%~dp0dist\THEOLOGICUS.exe" "%INSTALL_DIR%\dist\" >nul

:: Create desktop shortcut
echo [3/4] Creating shortcuts...
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Theologicus.lnk'); $Shortcut.TargetPath = '%INSTALL_DIR%\dist\THEOLOGICUS.exe'; $Shortcut.WorkingDirectory = '%INSTALL_DIR%'; $Shortcut.IconLocation = '%INSTALL_DIR%\config\jarvis.ico'; $Shortcut.Save()"

:: Create uninstaller
echo [4/4] Creating uninstaller...
(
echo @echo off
echo echo Uninstalling THEOLOGICUS...
echo rmdir /s /q "%INSTALL_DIR%"
echo del "%%USERPROFILE%%\Desktop\Theologicus.lnk" 2^>nul
echo echo THEOLOGICUS removed successfully.
echo pause
) > "%INSTALL_DIR%\uninstall.bat"

echo.
echo ========================================
echo   THEOLOGICUS v1.0.8 installed!
echo ========================================
echo Location: %INSTALL_DIR%
echo Desktop shortcut created.
echo.
echo To uninstall, run: %INSTALL_DIR%\uninstall.bat
echo.
pause
