@echo off
REM Audio Transcription Batch Script
REM This script checks for ffmpeg and runs the audio transcription script

where ffmpeg >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: ffmpeg is not installed or not in PATH
    echo.
    echo Please install ffmpeg with:
    echo   winget install ffmpeg
    echo.
    echo After installation, restart your terminal and run this script again.
    pause
    exit /b 1
)

echo Running audio transcription...
echo.

uv run audio_transcription.py

echo Done!
pause
