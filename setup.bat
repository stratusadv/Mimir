@echo off
::
:: Mimir Setup
::
:: Checks that this computer has everything Mimir needs, installs whatever is
:: missing, and offers to add Mimir to the Windows right-click menu.
::
:: Double-click it to run a full check with a report at the end. transcribe.bat
:: calls it as "setup.bat /quiet" before every transcription, which says
:: nothing at all when there is nothing to do, and "setup.bat /menu" to manage
:: the right-click menu on its own.
::
:: Exit code 0 means Mimir is ready to run. Anything else means it is not.
::
setlocal enabledelayedexpansion

title Mimir Setup

set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%~dp0app\"
set "TOOLS_DIR=%~dp0app\tools"
if exist "%TOOLS_DIR%\ffmpeg.exe" set "PATH=%TOOLS_DIR%;%PATH%"
if exist "%TOOLS_DIR%\ffmpeg\bin\ffmpeg.exe" set "PATH=%TOOLS_DIR%\ffmpeg\bin;%PATH%"

for /f %%e in ('echo prompt $E ^| cmd') do set "ESC=%%e"

set "C_ACCENT=%ESC%[96m"
set "C_FAIL=%ESC%[91m"
set "C_MUTED=%ESC%[90m"
set "C_OK=%ESC%[92m"
set "C_RESET=%ESC%[0m"
set "C_WARN=%ESC%[93m"
set "C_WHITE=%ESC%[97m"

set "AUDIO_EXTENSIONS=.flac .m4a .mp3 .mp4 .mpeg .ogg .wav .webm"
set "CLASSIC_MENU_KEY=HKCU\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"
set "ICON_FILE=%~dp0app\assets\mimir.ico"
set "LAUNCHER=%~dp0app\transcribe.bat"
set "MENU_LABEL=Transcribe with Mimir"
set "MENU_ROOT=HKCU\Software\Classes"
set "PYTHON_WANTED=>=3.11"
set "RULE=--------------------------------------------------------------------"
set "SETTINGS_KEY=HKCU\Software\Mimir"

set "exit_code=0"
set "quiet_mode=0"
if /i "%~1"=="/quiet" set "quiet_mode=1"
if /i "%~1"=="/menu" goto :menu_only

set "missing_count=0"
call :check_tool ffmpeg "Gyan.FFmpeg" "FFmpeg" "reads the audio"
call :check_tool uv "astral-sh.uv" "uv" "runs the transcriber"

if !missing_count! gtr 0 (
    call :install_missing
    if errorlevel 1 (
        set "exit_code=1"
        goto :finish
    )
)

call :ensure_python
if errorlevel 1 (
    set "exit_code=1"
    goto :finish
)

call :ensure_shortcut
call :ensure_menu_current
call :offer_context_menu

if !quiet_mode!==1 goto :finish

call :draw_report
goto :finish

:menu_only
call :toggle_context_menu
goto :finish

:check_tool
where %~1 >nul 2>nul
if not errorlevel 1 goto :eof
set /a missing_count+=1
set "missing_command_!missing_count!=%~1"
set "missing_id_!missing_count!=%~2"
set "missing_name_!missing_count!=%~3"
set "missing_note_!missing_count!=%~4"
goto :eof

:install_missing
cls
call :draw_header
set "plural=programs"
if !missing_count!==1 set "plural=program"
echo    !C_WARN!Mimir needs !missing_count! more free !plural! before it can run:!C_RESET!
echo.
for /l %%m in (1,1,!missing_count!) do echo      !C_ACCENT!-!C_RESET! !missing_name_%%m!   !C_MUTED!!missing_note_%%m!!C_RESET!
echo.
echo    !C_MUTED!These are installed once per computer, and Mimir can do it now.!C_RESET!
echo.

where winget >nul 2>nul
if errorlevel 1 (
    echo    !C_FAIL![ERROR]!C_RESET! This computer is missing the Windows App Installer,
    echo    !C_MUTED!so Mimir cannot install anything for you.!C_RESET!
    echo.
    echo    !C_MUTED!Get "App Installer" from the Microsoft Store, then run this again.!C_RESET!
    echo.
    pause
    exit /b 1
)

choice /c YN /n /m "   Install them now? [Y] yes   [N] quit: "
if errorlevel 2 exit /b 1

echo.
echo    !C_MUTED!!RULE!!C_RESET!
echo    !C_MUTED!Windows may ask for permission. Choose Yes.!C_RESET!
echo.

for /l %%m in (1,1,!missing_count!) do call :install_one %%m

call :refresh_path

set "still_missing=0"
for /l %%m in (1,1,!missing_count!) do (
    where !missing_command_%%m! >nul 2>nul
    if errorlevel 1 set /a still_missing+=1
)

if !still_missing! gtr 0 (
    echo    !C_WARN!Almost there.!C_RESET!
    echo    !C_MUTED!Close this window, then run Mimir again so Windows can pick up!C_RESET!
    echo    !C_MUTED!what was just installed.!C_RESET!
    echo.
    pause
    exit /b 1
)

exit /b 0

:install_one
echo    !C_ACCENT!Installing !missing_name_%~1! ...!C_RESET!
winget install --id !missing_id_%~1! --exact --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity
if errorlevel 1 (
    echo.
    echo    !C_FAIL![FAIL]!C_RESET! !missing_name_%~1! did not install.
) else (
    echo.
    echo    !C_OK![ OK ]!C_RESET! !missing_name_%~1! installed.
)
echo.
goto :eof

:ensure_python
uv python find "%PYTHON_WANTED%" >nul 2>nul
if not errorlevel 1 exit /b 0

cls
call :draw_header
echo    !C_WARN!Mimir needs Python, and this computer has no new enough copy.!C_RESET!
echo.
echo    !C_MUTED!Mimir keeps its own private copy, so nothing already installed!C_RESET!
echo    !C_MUTED!on this computer is touched or changed.!C_RESET!
echo.
echo    !C_ACCENT!Downloading Python ...!C_RESET!
echo.

uv python install

uv python find "%PYTHON_WANTED%" >nul 2>nul
if errorlevel 1 (
    echo.
    echo    !C_FAIL![FAIL]!C_RESET! Python could not be set up.
    echo    !C_MUTED!Check this computer can reach the internet, then try again.!C_RESET!
    echo.
    pause
    exit /b 1
)

echo.
echo    !C_OK![ OK ]!C_RESET! Python is ready.
echo.
timeout /t 2 /nobreak >nul 2>nul
exit /b 0

:refresh_path
set "machine_path="
set "user_path="
for /f "usebackq tokens=2,*" %%a in (`reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul ^| findstr /i /r /c:"REG_[A-Z_]*SZ"`) do set "machine_path=%%b"
for /f "usebackq tokens=2,*" %%a in (`reg query "HKCU\Environment" /v Path 2^>nul ^| findstr /i /r /c:"REG_[A-Z_]*SZ"`) do set "user_path=%%b"
if defined machine_path set "PATH=!PATH!;!machine_path!"
if defined user_path set "PATH=!PATH!;!user_path!"
call set "PATH=%PATH%"
if exist "%TOOLS_DIR%\ffmpeg.exe" set "PATH=%TOOLS_DIR%;%PATH%"
if exist "%TOOLS_DIR%\ffmpeg\bin\ffmpeg.exe" set "PATH=%TOOLS_DIR%\ffmpeg\bin;%PATH%"
goto :eof

:ensure_shortcut
if not exist "%ICON_FILE%" goto :eof
set "shortcut_file=%SCRIPT_DIR%Mimir.lnk"
set "shortcut_folder=%SCRIPT_DIR:~0,-1%"
set "stamped_target="
for /f "tokens=2,*" %%a in ('reg query "%SETTINGS_KEY%" /v ShortcutTarget 2^>nul ^| findstr /i ShortcutTarget') do set "stamped_target=%%b"
if exist "!shortcut_file!" if /i "!stamped_target!"=="%LAUNCHER%" goto :eof
powershell -NoProfile -ExecutionPolicy Bypass -Command "$shell = New-Object -ComObject WScript.Shell; $shortcut = $shell.CreateShortcut('!shortcut_file!'); $shortcut.TargetPath = '%LAUNCHER%'; $shortcut.WorkingDirectory = '!shortcut_folder!'; $shortcut.IconLocation = '%ICON_FILE%'; $shortcut.Description = 'Mimir - Audio Transcriber'; $shortcut.Save()" >nul 2>nul
if exist "!shortcut_file!" reg add "%SETTINGS_KEY%" /v ShortcutTarget /t REG_SZ /d "%LAUNCHER%" /f >nul 2>nul
goto :eof

:ensure_menu_current
reg query "%MENU_ROOT%\Directory\shell\Mimir" >nul 2>nul
if errorlevel 1 goto :eof
set "menu_command="
for /f "tokens=2,*" %%a in ('reg query "%MENU_ROOT%\Directory\shell\Mimir\command" /ve 2^>nul ^| findstr /i REG_SZ') do set "menu_command=%%b"
echo !menu_command! | find /i "%LAUNCHER%" >nul
if not errorlevel 1 goto :eof
call :write_verbs
goto :eof

:write_verbs
for %%x in (%AUDIO_EXTENSIONS%) do call :add_verb "%MENU_ROOT%\SystemFileAssociations\%%x\shell\Mimir" "!MENU_LABEL!" FILE

call :add_verb "%MENU_ROOT%\Directory\shell\Mimir" "!MENU_LABEL!" FILE
call :add_verb "%MENU_ROOT%\Directory\Background\shell\Mimir" "!MENU_LABEL!" DIRECTORY
call :add_verb "%MENU_ROOT%\DesktopBackground\Shell\Mimir" "Open Mimir" NONE
goto :eof

:offer_context_menu
reg query "%MENU_ROOT%\Directory\shell\Mimir" >nul 2>nul
if not errorlevel 1 goto :eof
reg query "%SETTINGS_KEY%" /v ContextMenuAsked >nul 2>nul
if not errorlevel 1 goto :eof

cls
call :draw_header
echo    !C_WHITE!Add Mimir to your right-click menu?!C_RESET!
echo.
echo    !C_MUTED!You could then right-click an audio file, a folder, or empty!C_RESET!
echo    !C_MUTED!space in any window, and pick "!MENU_LABEL!" straight!C_RESET!
echo    !C_MUTED!away, instead of hunting for Mimir first.!C_RESET!
echo.
echo    !C_MUTED!This changes your account only. Nothing extra is installed, and!C_RESET!
echo    !C_MUTED!you can take it back off any time by running setup.bat again.!C_RESET!
echo.

choice /c YN /n /m "   Add it? [Y] yes   [N] no thanks: "
set "menu_answer=!errorlevel!"

reg add "%SETTINGS_KEY%" /v ContextMenuAsked /t REG_SZ /d "1" /f >nul 2>nul

if !menu_answer!==2 goto :eof
call :install_context_menu
goto :eof

:toggle_context_menu
reg query "%MENU_ROOT%\Directory\shell\Mimir" >nul 2>nul
if errorlevel 1 (
    call :install_context_menu
) else (
    call :remove_context_menu
)
goto :eof

:install_context_menu
cls
call :draw_header
echo    !C_ACCENT!Adding Mimir to the right-click menu...!C_RESET!
echo.

call :write_verbs

echo    !C_OK![ OK ]!C_RESET! Right-click an audio file or a folder and look for
echo           !C_WHITE!"!MENU_LABEL!"!C_RESET!.
echo.

call :is_compact_menu
if not errorlevel 1 (
    echo    !C_MUTED!On Windows 11 it sits under "Show more options" at the bottom!C_RESET!
    echo    !C_MUTED!of the short menu. Shift+F10 opens that longer menu directly.!C_RESET!
    echo.
)

pause
goto :eof

:remove_context_menu
cls
call :draw_header
echo    !C_ACCENT!Removing Mimir from the right-click menu...!C_RESET!
echo.

for %%x in (%AUDIO_EXTENSIONS%) do reg delete "%MENU_ROOT%\SystemFileAssociations\%%x\shell\Mimir" /f >nul 2>nul

reg delete "%MENU_ROOT%\Directory\shell\Mimir" /f >nul 2>nul
reg delete "%MENU_ROOT%\Directory\Background\shell\Mimir" /f >nul 2>nul
reg delete "%MENU_ROOT%\DesktopBackground\Shell\Mimir" /f >nul 2>nul

echo    !C_OK![ OK ]!C_RESET! Mimir is no longer in the right-click menu.
echo.

reg query "%CLASSIC_MENU_KEY%\InprocServer32" >nul 2>nul
if not errorlevel 1 (
    echo    !C_MUTED!The full-length right-click menu is still switched on. To put!C_RESET!
    echo    !C_MUTED!Windows back the way it was, run setup.bat and choose it there.!C_RESET!
    echo.
)

pause
goto :eof

:add_verb
reg add "%~1" /ve /t REG_SZ /d "%~2" /f >nul
if exist "%ICON_FILE%" reg add "%~1" /v Icon /t REG_SZ /d "\"%ICON_FILE%\"" /f >nul
if "%~3"=="FILE" reg add "%~1" /v MultiSelectModel /t REG_SZ /d "Player" /f >nul
if "%~3"=="FILE" reg add "%~1\command" /ve /t REG_SZ /d "\"%LAUNCHER%\" \"%%1\"" /f >nul
if "%~3"=="DIRECTORY" reg add "%~1\command" /ve /t REG_SZ /d "\"%LAUNCHER%\" \"%%V\"" /f >nul
if "%~3"=="NONE" reg add "%~1\command" /ve /t REG_SZ /d "\"%LAUNCHER%\"" /f >nul
goto :eof

:is_compact_menu
set "build_number=0"
for /f "tokens=3" %%b in ('reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v CurrentBuildNumber 2^>nul ^| findstr /i CurrentBuildNumber') do set "build_number=%%b"
if !build_number! lss 22000 exit /b 1
reg query "%CLASSIC_MENU_KEY%\InprocServer32" >nul 2>nul
if not errorlevel 1 exit /b 1
exit /b 0

:enable_classic_menu
cls
call :draw_header
echo    !C_WHITE!Show Mimir in the first right-click menu!C_RESET!
echo.
echo    !C_MUTED!Windows 11 only lets apps installed from the Microsoft Store!C_RESET!
echo    !C_MUTED!into its short menu, so no script can put itself there. The!C_RESET!
echo    !C_MUTED!only way is to switch the short menu off, which brings back the!C_RESET!
echo    !C_MUTED!full-length menu Windows 10 had.!C_RESET!
echo.
echo    !C_WARN!Read this part before you say yes:!C_RESET!
echo      !C_MUTED!- It changes every right-click menu, not only Mimir.!C_RESET!
echo      !C_MUTED!- Your account only. Nobody else on this computer is affected.!C_RESET!
echo      !C_MUTED!- The screen flickers once while Windows restarts the desktop,!C_RESET!
echo      !C_MUTED!  and any open File Explorer windows will close.!C_RESET!
echo      !C_MUTED!- Undo it any time by running setup.bat again.!C_RESET!
echo.

choice /c YN /n /m "   Go ahead? [Y] yes   [N] leave Windows alone: "
if errorlevel 2 (
    echo.
    echo    !C_MUTED!Left alone. Mimir stays under "Show more options", or press!C_RESET!
    echo    !C_MUTED!Shift+F10 instead of right-clicking to skip straight to it.!C_RESET!
    echo.
    pause
    goto :eof
)

echo.
echo    !C_ACCENT!Switching the short menu off...!C_RESET!
reg add "%CLASSIC_MENU_KEY%\InprocServer32" /ve /t REG_SZ /d "" /f >nul
call :restart_explorer
echo    !C_OK![ OK ]!C_RESET! Right-click anything. Mimir is in the first menu now.
echo.
pause
goto :eof

:disable_classic_menu
echo.
echo    !C_ACCENT!Putting the Windows 11 short menu back...!C_RESET!
reg delete "%CLASSIC_MENU_KEY%" /f >nul 2>nul
call :restart_explorer
echo    !C_OK![ OK ]!C_RESET! The short menu is back. Mimir sits under "Show more options".
echo.
pause
goto :eof

:restart_explorer
taskkill /f /im explorer.exe >nul 2>nul
start "" explorer.exe
timeout /t 3 /nobreak >nul 2>nul
goto :eof

:draw_report
cls
call :draw_header
echo    !C_WHITE!Everything Mimir needs:!C_RESET!
echo.

call :draw_check ffmpeg "FFmpeg           " "reads the audio"
call :draw_check uv "uv               " "runs the transcriber"
call :draw_python_check

if exist "%APP_DIR%.env" (
    echo      !C_OK![ OK ]!C_RESET! Settings file     !C_MUTED!holds the service address and key!C_RESET!
) else (
    echo      !C_FAIL![ NO ]!C_RESET! Settings file     !C_MUTED!missing .env - see README.txt!C_RESET!
)

reg query "%MENU_ROOT%\Directory\shell\Mimir" >nul 2>nul
if errorlevel 1 (
    echo      !C_MUTED![ -- ] Right-click menu  not added!C_RESET!
) else (
    echo      !C_OK![ OK ]!C_RESET! Right-click menu  !C_MUTED!"!MENU_LABEL!"!C_RESET!
)

echo.
echo    !C_MUTED!!RULE!!C_RESET!
echo.

if not exist "%APP_DIR%.env" (
    echo    !C_WARN!Mimir cannot transcribe until the .env file is in place.!C_RESET!
    echo    !C_MUTED!Copy app\.env.example to app\.env and fill it in.!C_RESET!
    echo    !C_MUTED!See FIRST TIME SETUP in README.txt.!C_RESET!
    echo.
)

set "menu_installed=1"
reg query "%MENU_ROOT%\Directory\shell\Mimir" >nul 2>nul
if errorlevel 1 set "menu_installed=0"

set "classic_on=1"
reg query "%CLASSIC_MENU_KEY%\InprocServer32" >nul 2>nul
if errorlevel 1 set "classic_on=0"

if !menu_installed!==0 (
    choice /c MQ /n /m "   [M] add Mimir to the right-click menu   [Q] done: "
    if not errorlevel 2 call :install_context_menu
    goto :eof
)

if !classic_on!==1 (
    choice /c MSQ /n /m "   [M] remove from right-click   [S] bring back the short Windows 11 menu   [Q] done: "
    set "report_choice=!errorlevel!"
    if !report_choice!==1 call :remove_context_menu
    if !report_choice!==2 call :disable_classic_menu
    goto :eof
)

call :is_compact_menu
if errorlevel 1 (
    choice /c MQ /n /m "   [M] remove Mimir from the right-click menu   [Q] done: "
    if not errorlevel 2 call :remove_context_menu
    goto :eof
)

choice /c MFQ /n /m "   [M] remove from right-click   [F] show Mimir in the first menu   [Q] done: "
set "report_choice=!errorlevel!"
if !report_choice!==1 call :remove_context_menu
if !report_choice!==2 call :enable_classic_menu
goto :eof

:draw_check
where %~1 >nul 2>nul
if errorlevel 1 (
    echo      !C_FAIL![ NO ]!C_RESET! %~2 !C_MUTED!missing!C_RESET!
) else (
    echo      !C_OK![ OK ]!C_RESET! %~2 !C_MUTED!%~3!C_RESET!
)
goto :eof

:draw_python_check
uv python find "%PYTHON_WANTED%" >nul 2>nul
if errorlevel 1 (
    echo      !C_FAIL![ NO ]!C_RESET! Python            !C_MUTED!missing!C_RESET!
) else (
    echo      !C_OK![ OK ]!C_RESET! Python            !C_MUTED!a private copy, kept by uv!C_RESET!
)
goto :eof

:draw_header
echo.
echo    !C_ACCENT!!RULE!!C_RESET!
echo     !C_WHITE!MIMIR SETUP!C_RESET!  !C_MUTED!getting this computer ready!C_RESET!
echo    !C_ACCENT!!RULE!!C_RESET!
echo.
goto :eof

:finish
endlocal & set "PATH=%PATH%" & exit /b %exit_code%
