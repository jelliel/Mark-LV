; THEOLOGICUS Installer
; Generated for version 1.0.5

Name "THEOLOGICUS v1.0.5"
OutFile "THEOLOGICUS-v1.0.5-Setup.exe"
InstallDir "$PROGRAMFILES64\Theologicus"
RequestExecutionLevel admin
ShowInstDetails show
ShowUninstDetails show
SetCompressor lzma

; Pages
!include "MUI2.nsh"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "French"

; Icons
!define MUI_ICON "config\theologicus.ico"
!define MUI_UNICON "config\theologicus.ico"

; Install section
Section "THEOLOGICUS Core" SEC01
    SetOutPath "$INSTDIR"

    ; Main application files
    File "main.py"
    File "ui.py"
    File "ui_new.html"
    File "requirements.txt"
    File "readme.md"
    File "bump_version.py"

    ; Application executable
    SetOutPath "$INSTDIR\dist"
    File "dist\THEOLOGICUS.exe"

    ; Subdirectories
    SetOutPath "$INSTDIR\actions"
    File /r "actions\*.*"

    SetOutPath "$INSTDIR\config"
    File /r "config\*.*"

    SetOutPath "$INSTDIR\core"
    File /r "core\*.*"

    SetOutPath "$INSTDIR\dashboard"
    File /r "dashboard\*.*"

    SetOutPath "$INSTDIR\memory"
    File /r "memory\*.*"

    SetOutPath "$INSTDIR\research"
    File /r "research\*.*"

    ; Create uninstaller
    WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

; Start menu shortcuts
Section "-Shortcuts"
    CreateDirectory "$SMPROGRAMS\Theologicus"
    CreateShortcut "$SMPROGRAMS\Theologicus\Theologicus.lnk" "$INSTDIR\dist\THEOLOGICUS.exe" "" "$INSTDIR\config\theologicus.ico" 0
    CreateShortcut "$SMPROGRAMS\Theologicus\Uninstall.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\config\theologicus.ico" 0
SectionEnd

; Registry
Section
    WriteRegStr HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Theologicus" "DisplayName" "THEOLOGICUS v1.0.5"
    WriteRegStr HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Theologicus" "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Theologicus" "DisplayIcon" "$INSTDIR\config\theologicus.ico"
    WriteRegStr HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Theologicus" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Theologicus" "Publisher" "Theologicus AI"
SectionEnd

; Uninstall section
Section "Uninstall"
    ; Remove Start Menu
    Delete "$SMPROGRAMS\Theologicus\Theologicus.lnk"
    Delete "$SMPROGRAMS\Theologicus\Uninstall.lnk"
    RmDir "$SMPROGRAMS\Theologicus"

    ; Remove registry
    DeleteRegKey HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Theologicus"

    ; Remove files
    RMDir /r "$INSTDIR\actions"
    RMDir /r "$INSTDIR\config"
    RMDir /r "$INSTDIR\core"
    RMDir /r "$INSTDIR\dashboard"
    RMDir /r "$INSTDIR\memory"
    RMDir /r "$INSTDIR\research"
    RMDir /r "$INSTDIR\dist"
    Delete "$INSTDIR\*.py"
    Delete "$INSTDIR\*.html"
    Delete "$INSTDIR\*.txt"
    Delete "$INSTDIR\*.md"

    ; Remove directory
    RMDir "$INSTDIR"
SectionEnd
