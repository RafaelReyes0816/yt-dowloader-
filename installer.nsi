; NSIS Installer Script — YT-DownLoader del Jaeger
; Build with: makensis installer.nsi

!include "MUI2.nsh"

Name "YT-DownLoader del Jaeger"
OutFile "YT-DownLoader-Jaeger-Setup.exe"
InstallDir "$PROGRAMFILES\YT-DownLoader"
InstallDirRegKey HKLM "Software\YT-DownLoader" "InstallDir"
RequestExecutionLevel admin

; --- Interface Settings ---
!define MUI_ABORTWARNING
!define MUI_ICON "assets\icons\icon.ico"
!define MUI_UNICON "assets\icons\icon.ico"

; --- Pages ---
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; --- Languages ---
!insertmacro MUI_LANGUAGE "Spanish"

Section "Instalar"
  SetOutPath "$INSTDIR"
  File /r "dist\yt-dowloader\*.*"

  ; Shortcut escritorio
  CreateShortcut "$DESKTOP\YT-DownLoader.lnk" "$INSTDIR\yt-dowloader.exe"

  ; Shortcut menú inicio
  CreateDirectory "$SMPROGRAMS\YT-DownLoader"
  CreateShortcut "$SMPROGRAMS\YT-DownLoader\YT-DownLoader.lnk" "$INSTDIR\yt-dowloader.exe"
  CreateShortcut "$SMPROGRAMS\YT-DownLoader\Desinstalar.lnk" "$INSTDIR\uninstall.exe"

  ; Desinstalador
  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; Registro Windows
  WriteRegStr HKLM "Software\YT-DownLoader" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YT-DownLoader" \
    "DisplayName" "YT-DownLoader del Jaeger"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YT-DownLoader" \
    "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YT-DownLoader" \
    "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YT-DownLoader" \
    "DisplayVersion" "2.1.4"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YT-DownLoader" \
    "Publisher" "Rafael Reyes"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YT-DownLoader" \
    "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YT-DownLoader" \
    "NoRepair" 1
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\YT-DownLoader.lnk"
  RMDir /r "$SMPROGRAMS\YT-DownLoader"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YT-DownLoader"
  DeleteRegKey HKLM "Software\YT-DownLoader"
SectionEnd
