@echo off
::
:: Mimir Uninstall
::
:: Takes Mimir off this computer. It searches for every copy of the Mimir
:: folder, old and new, along with the right-click menu entries, the shortcuts,
:: and the settings Mimir keeps in the registry. It shows what it found and
:: asks before it removes anything.
::
:: Transcripts and notes are never touched. They sit beside the audio files
:: they came from, not inside the Mimir folder.
::
:: Double-click it. "uninstall.bat /deep" starts with the slow search of every
:: fixed drive, which is also offered from inside the script.
::
:: The removing is done by a staged copy of this file in the temp folder, so
:: the Mimir folder holding it can be deleted too. That copy is started as
:: "/apply".
::
:: Exit code 0 means everything that was chosen is gone. Anything else means
:: some of it is still there.
::
setlocal enabledelayedexpansion

title Mimir Uninstall

set "SCRIPT_DIR=%~dp0"

for /f %%e in ('echo prompt $E ^| cmd') do set "ESC=%%e"

set "C_ACCENT=%ESC%[96m"
set "C_FAIL=%ESC%[91m"
set "C_MUTED=%ESC%[90m"
set "C_OK=%ESC%[92m"
set "C_RESET=%ESC%[0m"
set "C_WARN=%ESC%[93m"
set "C_WHITE=%ESC%[97m"

set "CLASSIC_MENU_KEY=HKCU\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"
set "PREVIEW_LIMIT=12"
set "RULE=--------------------------------------------------------------------"
set "SETTINGS_BACKUP_DIR=%USERPROFILE%\Mimir-settings-backup"

if /i "%~1"=="/apply" goto :apply

set "deep_scan=0"
if /i "%~1"=="/deep" set "deep_scan=1"

where powershell >nul 2>nul
if errorlevel 1 (
    cls
    call :draw_header
    echo    !C_FAIL![FAIL]!C_RESET! Windows PowerShell was not found on this computer.
    echo    !C_MUTED!Mimir Uninstall needs it to search the drives and the registry.!C_RESET!
    echo.
    pause
    exit /b 1
)

for /d %%d in ("%TEMP%\mimir-uninstall-*") do rd /s /q "%%d" >nul 2>nul

set "WORK=%TEMP%\mimir-uninstall-%RANDOM%%RANDOM%"
mkdir "%WORK%" >nul 2>nul
if not exist "%WORK%" (
    cls
    call :draw_header
    echo    !C_FAIL![FAIL]!C_RESET! Could not create a temporary folder to work in.
    echo.
    pause
    exit /b 1
)

set "FOLDER_FILE=%WORK%\folders.txt"
set "MENU_FILE=%WORK%\menu.txt"
set "SHORTCUT_FILE=%WORK%\shortcuts.txt"

:scan
cls
call :draw_header
if !deep_scan!==1 (
    echo    !C_ACCENT!Searching every drive for Mimir. This can take a few minutes ...!C_RESET!
) else (
    echo    !C_ACCENT!Looking for Mimir on this computer ...!C_RESET!
)
echo.

call :find_folders
call :find_menu_entries
call :find_shortcuts
call :count_findings

if !folder_count!==0 if !menu_count!==0 if !shortcut_count!==0 goto :nothing_found

set "remove_folders=0"
set "remove_tools=0"
set "restore_menu=0"
set "user_quit=0"

call :ask_folders
if "!scan_again!"=="1" goto :scan
if "!user_quit!"=="1" goto :cancelled

if !classic_found!==1 call :ask_classic
call :ask_tools
call :confirm
if "!user_quit!"=="1" goto :cancelled

copy /y "%~f0" "%WORK%\uninstall.bat" >nul 2>nul
if not exist "%WORK%\uninstall.bat" (
    echo.
    echo    !C_FAIL![FAIL]!C_RESET! Could not prepare the uninstall.
    echo    !C_MUTED!Nothing has been changed.!C_RESET!
    echo.
    pause
    exit /b 1
)

echo.
echo    !C_OK![ OK ]!C_RESET! Removing in a new window ...
echo.
echo    !C_MUTED!This window closes now so the folder holding it can be deleted.!C_RESET!
echo.

start "Mimir Uninstall" /d "%TEMP%" cmd /c ""%WORK%\uninstall.bat" /apply "%WORK%" !remove_folders! !restore_menu! !remove_tools!"
exit /b 0

:nothing_found
cls
call :draw_header
echo    !C_OK![ OK ]!C_RESET! No trace of Mimir was found.
echo.
if !deep_scan!==1 (
    echo    !C_MUTED!Every fixed drive was searched. There is nothing to remove.!C_RESET!
    echo.
    rd /s /q "%WORK%" >nul 2>nul
    pause
    exit /b 0
)
echo    !C_MUTED!Only the usual places were searched: your user folder, OneDrive,!C_RESET!
echo    !C_MUTED!and the top of each drive.!C_RESET!
echo.
echo    !C_MUTED![D] searches every fixed drive, in case a copy is kept somewhere!C_RESET!
echo    !C_MUTED!unusual. This is slower.!C_RESET!
echo    !C_MUTED![Q] closes this window.!C_RESET!
echo.
choice /c DQ /n /m "   [D] Search everywhere   [Q] Quit: "
if errorlevel 2 (
    rd /s /q "%WORK%" >nul 2>nul
    exit /b 0
)
set "deep_scan=1"
goto :scan

:cancelled
cls
call :draw_header
echo    !C_MUTED!Nothing was changed. Mimir is exactly as it was.!C_RESET!
echo.
rd /s /q "%WORK%" >nul 2>nul
pause
exit /b 0

::
:: Writes every Mimir folder it can find to folders.txt, one path per line. A
:: folder counts as Mimir when it holds app\transcribe.bat or
:: app\audio_transcription.py, or the flat layout the first version shipped.
:: The registry is read as well, so a folder kept somewhere the search does not
:: reach is still found while the right-click menu points at it.
::
:find_folders
set "MIMIR_DEEP=!deep_scan!"
set "MIMIR_OUT=%FOLDER_FILE%"
set "MIMIR_SELF=%SCRIPT_DIR:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; $deep=($env:MIMIR_DEEP -eq '1'); if($deep){ $skip='^(Windows|Program Files|Program Files \(x86\)|ProgramData|\$Recycle\.Bin|System Volume Information|Recovery|node_modules|\.git)$' } else { $skip='^(AppData|Users|Windows|Program Files|Program Files \(x86\)|ProgramData|\$Recycle\.Bin|System Volume Information|Recovery|node_modules|\.git)$' }; $test={ param($folder) (Test-Path -LiteralPath (Join-Path $folder 'app\transcribe.bat')) -or (Test-Path -LiteralPath (Join-Path $folder 'app\audio_transcription.py')) -or ((Test-Path -LiteralPath (Join-Path $folder 'transcribe.bat')) -and (Test-Path -LiteralPath (Join-Path $folder 'audio_transcription.py'))) }; $targets=New-Object System.Collections.ArrayList; if($deep){ foreach($drive in [System.IO.DriveInfo]::GetDrives()){ if($drive.DriveType -eq 'Fixed' -and $drive.IsReady){ [void]$targets.Add(@{Path=$drive.RootDirectory.FullName;Depth=10}) } } } else { foreach($path in @($env:USERPROFILE,$env:PUBLIC,$env:OneDrive,$env:OneDriveCommercial)){ if($path){ [void]$targets.Add(@{Path=$path;Depth=4}) } }; foreach($drive in [System.IO.DriveInfo]::GetDrives()){ if($drive.DriveType -eq 'Fixed' -and $drive.IsReady){ [void]$targets.Add(@{Path=$drive.RootDirectory.FullName;Depth=1}) } } }; $hits=New-Object System.Collections.Generic.List[string]; foreach($target in $targets){ if(-not (Test-Path -LiteralPath $target.Path)){ continue }; if(& $test $target.Path){ [void]$hits.Add((Get-Item -LiteralPath $target.Path -Force).FullName) }; foreach($top in (Get-ChildItem -LiteralPath $target.Path -Directory -Force)){ if($top.Name -match $skip){ continue }; if(& $test $top.FullName){ [void]$hits.Add($top.FullName) }; foreach($sub in (Get-ChildItem -LiteralPath $top.FullName -Directory -Recurse -Depth $target.Depth -Force)){ if($sub.Name -match $skip){ continue }; if(& $test $sub.FullName){ [void]$hits.Add($sub.FullName) } } } }; foreach($clue in @($env:MIMIR_SELF,(Get-ItemProperty -LiteralPath 'HKCU:\Software\Mimir').ShortcutTarget,(Get-ItemProperty -LiteralPath 'HKCU:\Software\Classes\Directory\shell\Mimir\command').'(default)')){ if(-not $clue){ continue }; $clue=$clue.Replace([char]34,'').Trim(); $match=[regex]::Match($clue,'^([A-Za-z]:\\.+?)\\app\\[A-Za-z_]+\.bat'); $folder=$clue; if($match.Success){ $folder=$match.Groups[1].Value }; if((Test-Path -LiteralPath $folder) -and (& $test $folder)){ [void]$hits.Add((Get-Item -LiteralPath $folder -Force).FullName) } }; $unique=@($hits | Sort-Object -Unique); $final=New-Object System.Collections.Generic.List[string]; foreach($hit in $unique){ $nested=$false; foreach($other in $unique){ if($hit -ne $other -and $hit.StartsWith($other + '\',[System.StringComparison]::OrdinalIgnoreCase)){ $nested=$true } }; if(-not $nested){ [void]$final.Add($hit) } }; Set-Content -LiteralPath $env:MIMIR_OUT -Value $final -Encoding Oem" >nul 2>nul
set "MIMIR_DEEP="
set "MIMIR_OUT="
set "MIMIR_SELF="
goto :eof

::
:: Writes every registry key Mimir owns to menu.txt. Entries left by an older
:: version are caught as well, because every shell verb whose name starts with
:: Mimir is collected instead of a fixed list of keys.
::
:find_menu_entries
set "MIMIR_OUT=%MENU_FILE%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; $found=New-Object System.Collections.Generic.List[string]; $parents=New-Object System.Collections.Generic.List[string]; foreach($base in @('HKCU:\Software\Classes','HKLM:\Software\Classes')){ foreach($leaf in @('Directory\shell','Directory\Background\shell','DesktopBackground\Shell','Folder\shell','*\shell')){ [void]$parents.Add($base + '\' + $leaf) }; foreach($association in (Get-ChildItem -LiteralPath ($base + '\SystemFileAssociations'))){ [void]$parents.Add($association.PSPath + '\shell') } }; foreach($parent in $parents){ foreach($verb in (Get-ChildItem -LiteralPath $parent)){ if($verb.PSChildName -like 'Mimir*'){ [void]$found.Add($verb.Name) } } }; foreach($extra in @('HKCU:\Software\Mimir','HKLM:\Software\Mimir')){ if(Test-Path -LiteralPath $extra){ [void]$found.Add((Get-Item -LiteralPath $extra).Name) } }; Set-Content -LiteralPath $env:MIMIR_OUT -Value ($found | Sort-Object -Unique | ForEach-Object { $_ -replace '^HKEY_CURRENT_USER','HKCU' -replace '^HKEY_LOCAL_MACHINE','HKLM' -replace '^HKEY_CLASSES_ROOT','HKCR' }) -Encoding Oem" >nul 2>nul
set "MIMIR_OUT="
goto :eof

::
:: Writes every shortcut pointing at Mimir to shortcuts.txt. The desktop, the
:: start menu, the taskbar, and the Mimir folders themselves are checked, and a
:: shortcut counts only when its target is one of the Mimir launchers.
::
:find_shortcuts
set "MIMIR_FOLDER_FILE=%FOLDER_FILE%"
set "MIMIR_OUT=%SHORTCUT_FILE%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; $shell=New-Object -ComObject WScript.Shell; $folders=New-Object System.Collections.Generic.List[string]; foreach($path in @([Environment]::GetFolderPath('DesktopDirectory'),[Environment]::GetFolderPath('CommonDesktopDirectory'),[Environment]::GetFolderPath('Programs'),[Environment]::GetFolderPath('CommonPrograms'),[Environment]::GetFolderPath('Startup'),[Environment]::GetFolderPath('CommonStartup'),(Join-Path $env:APPDATA 'Microsoft\Internet Explorer\Quick Launch'))){ if($path){ [void]$folders.Add($path) } }; $known=New-Object System.Collections.Generic.List[string]; foreach($line in (Get-Content -LiteralPath $env:MIMIR_FOLDER_FILE)){ if($line){ [void]$folders.Add($line); [void]$known.Add($line) } }; $hits=New-Object System.Collections.Generic.List[string]; foreach($folder in ($folders | Sort-Object -Unique)){ if(-not (Test-Path -LiteralPath $folder)){ continue }; foreach($link in (Get-ChildItem -LiteralPath $folder -Filter '*.lnk' -Recurse -Depth 2 -Force)){ $target=($shell.CreateShortcut($link.FullName)).TargetPath; if(-not $target){ continue }; if($target -notmatch 'transcribe\.bat|search\.bat|audio_transcription\.py'){ continue }; $inside=$false; foreach($base in $known){ if($target.StartsWith($base + '\',[System.StringComparison]::OrdinalIgnoreCase)){ $inside=$true } }; if($inside -or $link.Name -eq 'Mimir.lnk'){ [void]$hits.Add($link.FullName) } } }; Set-Content -LiteralPath $env:MIMIR_OUT -Value ($hits | Sort-Object -Unique) -Encoding Oem" >nul 2>nul
set "MIMIR_FOLDER_FILE="
set "MIMIR_OUT="
goto :eof

:count_findings
call :count_lines "%FOLDER_FILE%" folder_count
call :count_lines "%MENU_FILE%" menu_count
call :count_lines "%SHORTCUT_FILE%" shortcut_count
set "classic_found=0"
reg query "%CLASSIC_MENU_KEY%\InprocServer32" >nul 2>nul
if not errorlevel 1 set "classic_found=1"
goto :eof

:count_lines
set "%~2=0"
if not exist "%~1" goto :eof
for /f "usebackq delims=" %%l in ("%~1") do set /a %~2+=1
goto :eof

:ask_folders
set "scan_again=0"
if !folder_count!==0 goto :ask_leftovers
cls
call :draw_header
call :draw_findings
echo    !C_MUTED!Transcripts and notes are not in these folders. They sit beside!C_RESET!
echo    !C_MUTED!the audio files they came from, and are left alone.!C_RESET!
echo.
echo    !C_MUTED!A settings file (app\.env) is copied to!C_RESET!
echo    !C_MUTED!%SETTINGS_BACKUP_DIR%!C_RESET!
echo    !C_MUTED!before its folder is deleted, in case Mimir is installed again.!C_RESET!
echo.
echo    !C_WARN!Deleting a Mimir folder cannot be undone.!C_RESET!
echo.
echo    !C_MUTED![Y] deletes the folders above, and removes the right-click menu,!C_RESET!
echo    !C_MUTED!the shortcuts, and the Mimir registry entries.!C_RESET!
echo    !C_MUTED![K] keeps the folders where they are, and removes only the!C_RESET!
echo    !C_MUTED!right-click menu, the shortcuts, and the registry entries.!C_RESET!
echo    !C_MUTED![D] searches every fixed drive first, in case another copy is!C_RESET!
echo    !C_MUTED!kept somewhere unusual. This is slower.!C_RESET!
echo    !C_MUTED![Q] closes this window and changes nothing.!C_RESET!
echo.
choice /c YKDQ /n /m "   [Y] Remove all   [K] Keep folders   [D] Search more   [Q] Quit: "
set "folder_answer=!errorlevel!"
if !folder_answer!==1 set "remove_folders=1"
if !folder_answer!==3 set "deep_scan=1"
if !folder_answer!==3 set "scan_again=1"
if !folder_answer! gtr 3 set "user_quit=1"
goto :eof

:ask_leftovers
cls
call :draw_header
call :draw_findings
echo    !C_MUTED!No Mimir folder was found, but the entries above are still on this!C_RESET!
echo    !C_MUTED!computer. They are what an older copy left behind when its folder!C_RESET!
echo    !C_MUTED!was deleted by hand, and they point nowhere.!C_RESET!
echo.
echo    !C_MUTED![Y] removes them.!C_RESET!
echo    !C_MUTED![D] searches every fixed drive first, in case the folder is kept!C_RESET!
echo    !C_MUTED!somewhere unusual. This is slower.!C_RESET!
echo    !C_MUTED![Q] closes this window and changes nothing.!C_RESET!
echo.
choice /c YDQ /n /m "   [Y] Remove them   [D] Search more   [Q] Quit: "
set "leftover_answer=!errorlevel!"
if !leftover_answer!==2 set "deep_scan=1"
if !leftover_answer!==2 set "scan_again=1"
if !leftover_answer! gtr 2 set "user_quit=1"
goto :eof

:ask_classic
cls
call :draw_header
echo    !C_WHITE!Put the short Windows 11 right-click menu back?!C_RESET!
echo.
echo    !C_MUTED!The full-length right-click menu is switched on for your account.!C_RESET!
echo    !C_MUTED!Mimir offers that during setup, so Mimir may be what turned it on!C_RESET!
echo    !C_MUTED!- or you did, for something else.!C_RESET!
echo.
echo    !C_MUTED![Y] puts the short menu back. The screen flickers once while!C_RESET!
echo    !C_MUTED!Windows restarts the desktop, and open File Explorer windows will!C_RESET!
echo    !C_MUTED!close.!C_RESET!
echo    !C_MUTED![N] leaves the right-click menu the way it is.!C_RESET!
echo.
choice /c YN /n /m "   [Y] Short menu back   [N] Leave it: "
set "classic_answer=!errorlevel!"
if !classic_answer!==1 set "restore_menu=1"
goto :eof

:ask_tools
set "tools_present=0"
where ffmpeg >nul 2>nul
if not errorlevel 1 set "tools_present=1"
where uv >nul 2>nul
if not errorlevel 1 set "tools_present=1"
if !tools_present!==0 goto :eof
cls
call :draw_header
echo    !C_WHITE!Remove FFmpeg and uv as well?!C_RESET!
echo.
echo    !C_MUTED!Mimir installed these two free programs, but they are ordinary!C_RESET!
echo    !C_MUTED!tools and something else on this computer may be using them.!C_RESET!
echo    !C_MUTED!Removing uv also removes the private Python it keeps and its!C_RESET!
echo    !C_MUTED!download cache.!C_RESET!
echo.
echo    !C_MUTED![N] leaves them installed. This is the safe answer.!C_RESET!
echo    !C_MUTED![Y] uninstalls FFmpeg and uv with winget as well.!C_RESET!
echo.
choice /c NY /n /m "   [N] Leave them   [Y] Remove them too: "
set "tools_answer=!errorlevel!"
if !tools_answer!==2 set "remove_tools=1"
goto :eof

:confirm
call :word_for !folder_count! "Mimir folder" "Mimir folders" folder_word
call :word_for !menu_count! "registry entry" "registry entries" menu_word
call :word_for !shortcut_count! "shortcut" "shortcuts" shortcut_word
cls
call :draw_header
echo    !C_WHITE!About to remove:!C_RESET!
echo.
if !menu_count! gtr 0 echo      !C_ACCENT!-!C_RESET! !menu_count! !menu_word!   !C_MUTED!right-click menu and settings!C_RESET!
if !shortcut_count! gtr 0 echo      !C_ACCENT!-!C_RESET! !shortcut_count! !shortcut_word!
if !remove_folders!==1 echo      !C_ACCENT!-!C_RESET! !folder_count! !folder_word!   !C_MUTED!deleted for good!C_RESET!
if !restore_menu!==1 echo      !C_ACCENT!-!C_RESET! the full-length right-click menu   !C_MUTED!the short menu returns!C_RESET!
if !remove_tools!==1 echo      !C_ACCENT!-!C_RESET! FFmpeg and uv   !C_MUTED!uninstalled with winget!C_RESET!
echo.
if !remove_folders!==0 if !folder_count!==1 (
    echo    !C_MUTED!The Mimir folder itself stays where it is.!C_RESET!
    echo.
)
if !remove_folders!==0 if !folder_count! gtr 1 (
    echo    !C_MUTED!The Mimir folders themselves stay where they are.!C_RESET!
    echo.
)
echo    !C_MUTED!!RULE!!C_RESET!
echo.
choice /c YN /n /m "   [Y] Go ahead   [N] Quit: "
set "confirm_answer=!errorlevel!"
if not !confirm_answer!==1 set "user_quit=1"
goto :eof

:word_for
if %~1==1 (
    set "%~4=%~2"
) else (
    set "%~4=%~3"
)
goto :eof

:draw_findings
echo    !C_WHITE!What was found:!C_RESET!
echo.
if !folder_count!==0 (
    echo      !C_MUTED!Mimir folders     none!C_RESET!
) else (
    echo      !C_WHITE!Mimir folders!C_RESET!     !C_MUTED!!folder_count!!C_RESET!
)
set "shown=0"
if exist "%FOLDER_FILE%" for /f "usebackq delims=" %%f in ("%FOLDER_FILE%") do call :draw_folder_line "%%f"
if !folder_count! gtr %PREVIEW_LIMIT% (
    set /a hidden_count=!folder_count!-%PREVIEW_LIMIT%
    echo        !C_MUTED!and !hidden_count! more!C_RESET!
)
echo.
if !menu_count!==0 (
    echo      !C_MUTED!Registry entries  none!C_RESET!
) else (
    echo      !C_WHITE!Registry entries!C_RESET!  !C_MUTED!!menu_count!   right-click menu and settings!C_RESET!
)
if !shortcut_count!==0 (
    echo      !C_MUTED!Shortcuts         none!C_RESET!
) else (
    echo      !C_WHITE!Shortcuts!C_RESET!         !C_MUTED!!shortcut_count!!C_RESET!
)
echo.
echo    !C_MUTED!!RULE!!C_RESET!
echo.
goto :eof

:draw_folder_line
set /a shown+=1
if !shown! gtr %PREVIEW_LIMIT% goto :eof
echo        !C_MUTED!%~1!C_RESET!
goto :eof

::
:: The staged half of the uninstall, running from the temp folder so that the
:: Mimir folder holding the original copy can be deleted.
::
:apply
set "WORK=%~2"
set "remove_folders=%~3"
set "restore_menu=%~4"
set "remove_tools=%~5"

set "FOLDER_FILE=%WORK%\folders.txt"
set "MENU_FILE=%WORK%\menu.txt"
set "SHORTCUT_FILE=%WORK%\shortcuts.txt"

set "exit_code=0"
set "folder_failed=0"
set "menu_failed=0"
set "settings_saved=0"
set "shortcut_failed=0"

call :count_lines "%FOLDER_FILE%" folder_count
call :count_lines "%MENU_FILE%" menu_count
call :count_lines "%SHORTCUT_FILE%" shortcut_count

cls
call :draw_header
echo    !C_ACCENT!Removing Mimir ...!C_RESET!
echo.

timeout /t 2 /nobreak >nul 2>nul

call :remove_menu_entries
call :remove_shortcuts
call :remove_temp_files
if !remove_folders!==1 call :delete_folders
if !restore_menu!==1 call :restore_short_menu
if !remove_tools!==1 call :remove_tools

call :draw_summary
pause
exit /b !exit_code!

:remove_menu_entries
if not exist "%MENU_FILE%" goto :eof
for /f "usebackq delims=" %%k in ("%MENU_FILE%") do call :delete_key "%%k"
goto :eof

:delete_key
reg query "%~1" >nul 2>nul
if errorlevel 1 goto :eof
reg delete "%~1" /f >nul 2>nul
reg query "%~1" >nul 2>nul
if not errorlevel 1 set /a menu_failed+=1
goto :eof

:remove_shortcuts
if not exist "%SHORTCUT_FILE%" goto :eof
for /f "usebackq delims=" %%s in ("%SHORTCUT_FILE%") do call :delete_shortcut "%%s"
goto :eof

:delete_shortcut
if not exist "%~1" goto :eof
del /f /q "%~1" >nul 2>nul
if exist "%~1" set /a shortcut_failed+=1
goto :eof

:remove_temp_files
for /d %%d in ("%TEMP%\mimir-update-*") do rd /s /q "%%d" >nul 2>nul
del /f /q "%TEMP%\mimir_queue_*.txt" >nul 2>nul
del /f /q "%TEMP%\mimir_result_*.txt" >nul 2>nul
goto :eof

:delete_folders
if not exist "%FOLDER_FILE%" goto :eof
for /f "usebackq delims=" %%f in ("%FOLDER_FILE%") do call :delete_folder "%%f"
goto :eof

:delete_folder
if not exist "%~1\" goto :eof
call :save_settings "%~1"
rd /s /q "%~1" >nul 2>nul
if exist "%~1\" set /a folder_failed+=1
goto :eof

::
:: Keeps a copy of the address and key before the folder goes, so installing
:: Mimir again is a matter of putting the file back.
::
:save_settings
set "settings_file=%~1\app\.env"
if not exist "!settings_file!" set "settings_file=%~1\.env"
if not exist "!settings_file!" goto :eof
if not exist "%SETTINGS_BACKUP_DIR%" mkdir "%SETTINGS_BACKUP_DIR%" >nul 2>nul
if not exist "%SETTINGS_BACKUP_DIR%" goto :eof
set /a settings_saved+=1
copy /y "!settings_file!" "%SETTINGS_BACKUP_DIR%\mimir-!settings_saved!.env" >nul 2>nul
goto :eof

:restore_short_menu
reg delete "%CLASSIC_MENU_KEY%" /f >nul 2>nul
taskkill /f /im explorer.exe >nul 2>nul
start "" explorer.exe
timeout /t 3 /nobreak >nul 2>nul
goto :eof

::
:: FFmpeg and uv are ordinary programs Mimir installed with winget, and are
:: only touched when they were explicitly asked for. uv is cleared out first,
:: so its private Python and its cache do not outlive it.
::
:remove_tools
echo    !C_ACCENT!Removing FFmpeg and uv ...!C_RESET!
echo.
where uv >nul 2>nul
if not errorlevel 1 call :clear_uv_data
winget uninstall --id astral-sh.uv --exact --source winget --silent --disable-interactivity --accept-source-agreements >nul 2>nul
winget uninstall --id Gyan.FFmpeg --exact --source winget --silent --disable-interactivity --accept-source-agreements >nul 2>nul
goto :eof

:clear_uv_data
uv cache clean >nul 2>nul
for /f "usebackq delims=" %%p in (`uv python dir 2^>nul`) do rd /s /q "%%p" >nul 2>nul
for /f "usebackq delims=" %%p in (`uv tool dir 2^>nul`) do rd /s /q "%%p" >nul 2>nul
goto :eof

:draw_summary
call :word_for !folder_failed! "folder" "folders" folder_word
call :word_for !menu_failed! "entry" "entries" menu_word
call :word_for !shortcut_failed! "shortcut" "shortcuts" shortcut_word
cls
call :draw_header

if !menu_count!==0 (
    echo      !C_MUTED![ -- ] No registry entries to remove!C_RESET!
) else if !menu_failed!==0 (
    echo      !C_OK![ OK ]!C_RESET! Right-click menu and registry entries removed
) else (
    echo      !C_WARN![WARN]!C_RESET! !menu_failed! registry !menu_word! could not be removed.
    echo             !C_MUTED!They belong to every user on this computer. Right-click!C_RESET!
    echo             !C_MUTED!uninstall.bat, choose "Run as administrator", and run it!C_RESET!
    echo             !C_MUTED!again to clear them.!C_RESET!
    set "exit_code=1"
)

if !shortcut_count!==0 (
    echo      !C_MUTED![ -- ] No shortcuts to remove!C_RESET!
) else if !shortcut_failed!==0 (
    echo      !C_OK![ OK ]!C_RESET! Shortcuts removed
) else (
    echo      !C_WARN![WARN]!C_RESET! !shortcut_failed! !shortcut_word! could not be deleted.
    set "exit_code=1"
)

if !remove_folders!==0 (
    echo      !C_MUTED![ -- ] Mimir folders left where they are!C_RESET!
) else if !folder_failed!==0 (
    echo      !C_OK![ OK ]!C_RESET! Mimir folders deleted
) else (
    echo      !C_WARN![WARN]!C_RESET! !folder_failed! !folder_word! could not be deleted.
    echo             !C_MUTED!Close any Mimir window, and any program holding a file!C_RESET!
    echo             !C_MUTED!open in that folder, then run uninstall.bat again.!C_RESET!
    set "exit_code=1"
)

if !restore_menu!==1 echo      !C_OK![ OK ]!C_RESET! The short Windows 11 right-click menu is back
if !remove_tools!==1 echo      !C_OK![ OK ]!C_RESET! FFmpeg and uv uninstalled

echo.
echo    !C_MUTED!!RULE!!C_RESET!
echo.

if !settings_saved! gtr 0 (
    echo    !C_MUTED!Your settings were copied to!C_RESET!
    echo    !C_MUTED!%SETTINGS_BACKUP_DIR%!C_RESET!
    echo.
)

echo    !C_MUTED!Transcripts and notes were not touched. They are still beside the!C_RESET!
echo    !C_MUTED!audio files they came from.!C_RESET!
echo.
echo    !C_MUTED!To install Mimir again, download the latest release from!C_RESET!
echo    !C_MUTED!https://github.com/stratusadv/Mimir/releases/latest and run!C_RESET!
echo    !C_MUTED!setup.bat.!C_RESET!
echo.
goto :eof

:draw_header
echo.
echo    !C_ACCENT!!RULE!!C_RESET!
echo     !C_WHITE!MIMIR UNINSTALL!C_RESET!  !C_MUTED!taking Mimir off this computer!C_RESET!
echo    !C_ACCENT!!RULE!!C_RESET!
echo.
goto :eof
