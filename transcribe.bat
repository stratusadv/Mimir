@echo off
::
:: Mimir - Audio Transcriber
::
:: Drag one or more audio files, or a folder of them, onto this script. Each
:: file is transcribed and the text is written beside the audio file. An
:: existing transcript is never overwritten: a numbered suffix is added.
::
:: Needs ffmpeg and uv on the machine, or an ffmpeg.exe in a "tools" folder
:: beside this script. See README.txt.
::
setlocal enabledelayedexpansion

title Mimir - Audio Transcriber

set "SCRIPT_DIR=%~dp0"
set "TOOLS_DIR=%~dp0tools"
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

set "AUDIO=;.flac;.m4a;.mp3;.mp4;.mpeg;.ogg;.wav;.webm;"
set "LIST_FILE=%TEMP%\mimir_queue_%RANDOM%%RANDOM%.txt"
set "PREVIEW_LIMIT=12"
set "RESULT_FILE=%TEMP%\mimir_result_%RANDOM%%RANDOM%.txt"
set "RULE=--------------------------------------------------------------------"

call :ensure_dependencies
if errorlevel 1 goto :terminate

if not exist "%SCRIPT_DIR%.env" (
    cls
    echo.
    echo    !C_FAIL![ERROR]!C_RESET! Missing settings file.
    echo.
    echo    !C_MUTED!A file named .env must sit beside this script, holding the!C_RESET!
    echo    !C_MUTED!transcription service address and key. See README.txt.!C_RESET!
    echo.
    pause
    goto :terminate
)

set "file_count=0"
set "skipped_count=0"

:collect_arguments
if "%~1"=="" goto :arguments_collected
if exist "%~1\" (
    call :add_folder "%~1"
) else (
    if exist "%~1" call :add_file "%~1"
)
shift
goto :collect_arguments

:arguments_collected
if not !file_count!==0 goto :menu

:prompt_for_file
cls
call :draw_header
echo    !C_WARN!No audio files were dropped onto this script.!C_RESET!
echo    !C_MUTED!Drop audio files or a folder next time, or type a path below.!C_RESET!
echo.
set "manual_path="
set /p "manual_path=   Path (blank to quit): "
if not defined manual_path goto :terminate
set "manual_path=!manual_path:"=!"
if exist "!manual_path!\" (
    call :add_folder "!manual_path!"
) else (
    if exist "!manual_path!" call :add_file "!manual_path!"
)
if !file_count!==0 goto :prompt_for_file

:menu
cls
call :draw_header
call :draw_files
echo.

choice /c SQ /n /m "   [S] Start transcribing   [Q] Quit: "
if errorlevel 2 goto :terminate

if exist "%LIST_FILE%" del /q "%LIST_FILE%" >nul 2>nul
for /l %%i in (1,1,!file_count!) do >>"%LIST_FILE%" echo !input_%%i!

cls
call :draw_header
echo    !C_ACCENT!Transcribing !file_count!. This can take a few minutes.!C_RESET!
echo.

set "MIMIR_RESULT_FILE=%RESULT_FILE%"
uv run --script "%SCRIPT_DIR%audio_transcription.py" "%LIST_FILE%"

del /q "%LIST_FILE%" >nul 2>nul
echo.

choice /c ORQ /n /m "   [O] open folder   [R] transcribe again   [Q] quit: "
if errorlevel 3 goto :terminate
if errorlevel 2 goto :menu
if exist "%RESULT_FILE%" (
    for /f "usebackq delims=" %%r in ("%RESULT_FILE%") do start "" explorer.exe /select,"%%r"
)
goto :terminate

:add_file
set "candidate_extension=%~x1"
if "!AUDIO:;%~x1;=!"=="!AUDIO!" (
    set /a skipped_count+=1
    goto :eof
)
set /a file_count+=1
set "input_!file_count!=%~f1"
goto :eof

:add_folder
for %%f in ("%~1\*") do call :add_file "%%~ff"
goto :eof

:draw_files
echo    !C_WHITE!Queued: !file_count!!C_RESET!
set "shown=0"
for /l %%i in (1,1,!file_count!) do (
    if !shown! lss %PREVIEW_LIMIT% (
        set /a shown+=1
        call :draw_file_row "!input_%%i!"
    )
)
if !file_count! gtr %PREVIEW_LIMIT% (
    set /a hidden=!file_count!-%PREVIEW_LIMIT%
    echo      !C_MUTED!... and !hidden! more!C_RESET!
)
if !skipped_count! gtr 0 (
    echo.
    echo    !C_WARN!!skipped_count! ignored - not audio files.!C_RESET!
)
goto :eof

:draw_file_row
set "row_name=%~nx1"
echo      !C_MUTED!-!C_RESET! !row_name!
goto :eof

:draw_header
echo.
echo    !C_ACCENT!!RULE!!C_RESET!
echo     !C_WHITE!MIMIR!C_RESET!  !C_MUTED!audio to text!C_RESET!
echo    !C_ACCENT!!RULE!!C_RESET!
echo.
goto :eof

:check_tool
where %~1 >nul 2>nul
if not errorlevel 1 goto :eof
set /a missing_count+=1
set "missing_command_!missing_count!=%~1"
set "missing_id_!missing_count!=%~2"
set "missing_name_!missing_count!=%~3"
set "missing_note_!missing_count!=%~4"
goto :eof

:ensure_dependencies
set "missing_count=0"
call :check_tool ffmpeg "Gyan.FFmpeg" "FFmpeg" "reads the audio"
call :check_tool uv "astral-sh.uv" "uv" "runs the transcriber"
if !missing_count!==0 exit /b 0

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
    echo    !C_MUTED!Close this window, then run transcribe.bat again so Windows can!C_RESET!
    echo    !C_MUTED!pick up what was just installed.!C_RESET!
    echo.
    pause
    exit /b 1
)

echo    !C_OK!Everything is ready.!C_RESET!
echo.
timeout /t 2 /nobreak >nul 2>nul
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

:refresh_path
set "machine_path="
set "user_path="
for /f "usebackq tokens=2,*" %%a in (`reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul ^| findstr /i /r /c:"REG_[A-Z_]*SZ"`) do set "machine_path=%%b"
for /f "usebackq tokens=2,*" %%a in (`reg query "HKCU\Environment" /v Path 2^>nul ^| findstr /i /r /c:"REG_[A-Z_]*SZ"`) do set "user_path=%%b"
if defined machine_path call set "PATH=%%machine_path%%;%%user_path%%"
if exist "%TOOLS_DIR%\ffmpeg.exe" set "PATH=%TOOLS_DIR%;%PATH%"
if exist "%TOOLS_DIR%\ffmpeg\bin\ffmpeg.exe" set "PATH=%TOOLS_DIR%\ffmpeg\bin;%PATH%"
goto :eof

:terminate
del /q "%LIST_FILE%" >nul 2>nul
del /q "%RESULT_FILE%" >nul 2>nul
echo !C_RESET!
endlocal
exit /b 0
