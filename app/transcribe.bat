@echo off
::
:: Mimir - Audio Transcriber
::
:: Drag one or more audio files, or a folder of them, onto this script. Each
:: file is transcribed and the text is written beside the audio file. An
:: existing transcript is never overwritten: a numbered suffix is added.
::
:: Everything it needs is checked and installed by setup.bat, which runs
:: quietly before each transcription. See README.md.
::
setlocal enabledelayedexpansion

title Mimir - Audio Transcriber

set "SCRIPT_DIR=%~dp0"
set "SETUP_FILE=%~dp0..\setup.bat"
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

if not exist "%SETUP_FILE%" (
    echo.
    echo    !C_FAIL![ERROR]!C_RESET! setup.bat is missing from the Mimir folder.
    echo    !C_MUTED!Copy the whole Mimir folder, not just this file.!C_RESET!
    echo.
    pause
    goto :terminate
)

call "%SETUP_FILE%" /quiet
if errorlevel 1 goto :terminate

set "update_available=0"
set "installed_version="
set "latest_version="
if exist "%SCRIPT_DIR%version_check.bat" call "%SCRIPT_DIR%version_check.bat"

if not exist "%SCRIPT_DIR%.env" (
    cls
    echo.
    echo    !C_FAIL![ERROR]!C_RESET! Missing settings file.
    echo.
    echo    !C_MUTED!A file named .env must sit beside this script, holding the!C_RESET!
    echo    !C_MUTED!transcription service address and key. Copy .env.example!C_RESET!
    echo    !C_MUTED!to .env and fill it in. See README.md.!C_RESET!
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
echo.
echo    !C_MUTED!Type or paste the path of an audio file, or a folder of them.!C_RESET!
echo    !C_MUTED!Leave it blank to close this window. Next time you can drop!C_RESET!
echo    !C_MUTED!files or a folder onto Mimir instead.!C_RESET!
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
echo    !C_MUTED![S] writes a word-for-word transcript beside the audio (_transcript.txt).!C_RESET!
echo    !C_MUTED![N] writes one notes file beside the audio (_notes.txt): a short!C_RESET!
echo    !C_MUTED!summary, action items, and a tidied-up transcript. The raw!C_RESET!
echo    !C_MUTED!transcript is not kept.!C_RESET!
echo    !C_MUTED![B] writes both files: the word-for-word transcript and the notes.!C_RESET!
echo    !C_MUTED!N and B take one extra AI pass, so they cost a little more and!C_RESET!
echo    !C_MUTED!finish a little later.!C_RESET!
echo    !C_MUTED![M] adds or removes Mimir in the Windows right-click menu!C_RESET!
echo    !C_MUTED!("Transcribe with Mimir" on audio, "Search with Mimir" on!C_RESET!
echo    !C_MUTED!.txt / .docx / .md), then comes back here. Nothing is transcribed.!C_RESET!
echo    !C_MUTED![Q] closes this window. Nothing is transcribed and your files!C_RESET!
echo    !C_MUTED!are left alone.!C_RESET!
echo.

choice /c SNBMQ /n /m "   [S] Transcript   [N] Notes   [B] Both   [M] Right-click menu   [Q] Quit: "
set "picked=!errorlevel!"
if !picked!==5 goto :terminate
if !picked!==4 (
    call "%SETUP_FILE%" /menu
    goto :menu
)

set "MIMIR_OUTPUT_MODE=transcript"
if !picked!==2 set "MIMIR_OUTPUT_MODE=notes"
if !picked!==3 set "MIMIR_OUTPUT_MODE=both"
set "MIMIR_SEARCH_QUERY="

if not "!MIMIR_OUTPUT_MODE!"=="transcript" (
    echo.
    echo    !C_MUTED!After notes are written, Mimir can search them and add!C_RESET!
    echo    !C_MUTED!highlights to the summary. Type what you want to find, in!C_RESET!
    echo    !C_MUTED!plain language, or leave blank to skip.!C_RESET!
    echo.
    set "search_query="
    set /p "search_query=   Search notes for (blank to skip): "
    set "search_query=!search_query:"=!"
    set "MIMIR_SEARCH_QUERY=!search_query!"
)

if exist "%LIST_FILE%" del /q "%LIST_FILE%" >nul 2>nul
for /l %%i in (1,1,!file_count!) do >>"%LIST_FILE%" echo !input_%%i!

cls
call :draw_header
echo    !C_ACCENT!Transcribing !file_count!. This can take a few minutes.!C_RESET!
if not "!MIMIR_OUTPUT_MODE!"=="transcript" echo    !C_MUTED!Notes are on; the extra pass runs after each transcript.!C_RESET!
if not "!MIMIR_SEARCH_QUERY!"=="" echo    !C_MUTED!Search highlights will be added to the notes summary.!C_RESET!
echo.

set "MIMIR_RESULT_FILE=%RESULT_FILE%"
uv run --script "%SCRIPT_DIR%audio_transcription.py" "%LIST_FILE%"

del /q "%LIST_FILE%" >nul 2>nul
echo.

call :load_results
call :draw_ai_warning

:finish_menu
if !result_count!==0 (
    echo    !C_MUTED![R] goes back to the output menu so you can try these files!C_RESET!
    echo    !C_MUTED!again.!C_RESET!
    echo    !C_MUTED![Q] closes this window.!C_RESET!
    echo.
    choice /c RQ /n /m "   [R] Transcribe again   [Q] Quit: "
    if errorlevel 2 goto :terminate
    goto :menu
)

echo    !C_MUTED![T] opens the text that was just written. If more than one file!C_RESET!
echo    !C_MUTED!was written, you pick which. Then this window closes.!C_RESET!
echo    !C_MUTED![O] opens the folder the text was saved in, with the first file!C_RESET!
echo    !C_MUTED!selected. Then this window closes.!C_RESET!
echo    !C_MUTED![R] goes back to the output menu so you can transcribe these!C_RESET!
echo    !C_MUTED!same files again, with a different choice if you want.!C_RESET!
echo    !C_MUTED![Q] closes this window.!C_RESET!
echo.

choice /c TORQ /n /m "   [T] Open result   [O] Open folder   [R] Transcribe again   [Q] Quit: "
set "finish_picked=!errorlevel!"
if !finish_picked!==4 goto :terminate
if !finish_picked!==3 goto :menu
if !finish_picked!==2 (
    start "" explorer.exe /select,"!result_1!"
    goto :terminate
)
set "transcript_opened=0"
call :open_transcript
if !transcript_opened!==1 goto :terminate
cls
call :draw_header
goto :finish_menu

:load_results
set "result_count=0"
if not exist "%RESULT_FILE%" goto :eof
for /f "usebackq delims=" %%r in ("%RESULT_FILE%") do (
    set /a result_count+=1
    set "result_!result_count!=%%~fr"
)
goto :eof

:open_transcript
if !result_count!==1 (
    start "" "!result_1!"
    set "transcript_opened=1"
    goto :eof
)

:open_transcript_prompt
cls
call :draw_header
echo    !C_WHITE!Files: !result_count!!C_RESET!
for /l %%i in (1,1,!result_count!) do call :draw_result_row %%i
echo.
echo    !C_MUTED!Type the number of the file to open in your default editor.!C_RESET!
echo    !C_MUTED!Then this window closes. Leave it blank to go back.!C_RESET!
echo.
set "pick="
set /p "pick=   Number to open (blank to go back): "
if not defined pick goto :eof
set "pick=!pick:"=!"
echo(!pick!|findstr /r "^[1-9][0-9]*$" >nul
if errorlevel 1 goto :open_transcript_retry
if !pick! gtr !result_count! goto :open_transcript_retry
call set "open_target=%%result_!pick!%%"
start "" "!open_target!"
set "transcript_opened=1"
goto :eof

:open_transcript_retry
echo.
echo    !C_WARN!Enter a number between 1 and !result_count!.!C_RESET!
timeout /t 2 /nobreak >nul
goto :open_transcript_prompt

:draw_result_row
call set "row_path=%%result_%1%%"
for %%p in ("!row_path!") do echo      !C_MUTED![%1]!C_RESET! %%~nxp
goto :eof

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

:draw_ai_warning
echo    !C_WARN!AI can make mistakes. Review the transcript before you rely on it.!C_RESET!
echo.
goto :eof

:draw_header
echo.
echo    !C_ACCENT!!RULE!!C_RESET!
echo     !C_WHITE!MIMIR!C_RESET!  !C_MUTED!audio to text!C_RESET!
echo    !C_ACCENT!!RULE!!C_RESET!
call :draw_update_banner
call :draw_ai_warning
goto :eof

:draw_update_banner
if not "%update_available%"=="1" goto :eof
echo    !C_WARN!Update available: !latest_version!!C_RESET! !C_MUTED!(this folder is !installed_version!)!C_RESET!
echo    !C_MUTED!Double-click update.bat in the Mimir folder to get it.!C_RESET!
echo.
goto :eof

:terminate
del /q "%LIST_FILE%" >nul 2>nul
del /q "%RESULT_FILE%" >nul 2>nul
echo !C_RESET!
endlocal
exit /b 0
