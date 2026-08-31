====================================================================
 MIMIR - AUDIO TO TEXT
====================================================================

Mimir turns recordings into text files. Drop an audio file on it and
a plain text transcript appears right next to that file.


--------------------------------------------------------------------
 HOW TO USE IT
--------------------------------------------------------------------

1. Find the file called "transcribe.bat" in this folder.

2. Drag your audio file (or a whole folder of them) on top of
   "transcribe.bat" and let go.

3. A black window opens and lists what it is about to transcribe.
   Press S to start, or Q to quit.

4. Wait. A percentage counts up for each file. A one hour recording
   usually takes a couple of minutes.

5. When it finishes you can press O to open the folder with your new
   transcript in it, R to transcribe something else, or Q to close.

You can also just double-click "transcribe.bat" and type or paste a
file path when it asks.


--------------------------------------------------------------------
 WHERE THE TEXT GOES
--------------------------------------------------------------------

The transcript is saved beside the audio file, with the same name
plus "_transcript.txt".

    meeting notes.mp3   ->   meeting_notes_transcript.txt

Nothing is ever overwritten. If a transcript with that name already
exists, the new one gets a number:

    meeting_notes_transcript (1).txt

Each sentence is put on its own line so the text is easy to skim and
easy to search.


--------------------------------------------------------------------
 WHAT KINDS OF FILES WORK
--------------------------------------------------------------------

    .flac   .m4a   .mp3   .mp4   .mpeg   .ogg   .wav   .webm

Anything else in a dropped folder is ignored, and the window tells
you how many files it skipped.


--------------------------------------------------------------------
 FIRST TIME SETUP
--------------------------------------------------------------------

There is nothing to install by hand.

The first time you run Mimir on a computer it checks for the two free
programs it depends on:

    FFmpeg    reads the audio
    uv        runs the transcriber

If either one is missing, Mimir lists it and asks:

    Install them now? [Y] yes   [N] quit

Press Y. Mimir installs them for you, and Windows may pop up a box
asking for permission - choose Yes. When it finishes, Mimir carries
straight on to the transcribing screen.

Very occasionally Windows needs the window closed and reopened before
it notices the new programs. Mimir will say so if that happens. Just
run transcribe.bat again.

There must also be a file called ".env" sitting in this folder. It
holds the address and key for the transcription service:

    AI_API_KEY=your-key-here
    AI_API_HOST=https://your-service-address
    LLM_AUDIO_MODEL=stratus.listen

That one Mimir cannot create for you. Do not share it, and do not put
it on the internet. It is the key to the account.


--------------------------------------------------------------------
 IF SOMETHING GOES WRONG
--------------------------------------------------------------------

"FFmpeg did not install" or "uv did not install"
    The install was cancelled, or the computer has no internet. Try
    running transcribe.bat again.

"This computer is missing the Windows App Installer"
    Mimir cannot install anything without it. Open the Microsoft
    Store, search for "App Installer", install it, and try again.

"Missing settings file"
    The .env file is not in this folder. Copy the whole Mimir folder,
    not just transcribe.bat.

"No API settings were found"
    The .env file is there but a line is blank or misspelled.

"ffmpeg could not read this file"
    The recording is damaged, or the file is not really audio.

"the service returned no words for this audio"
    The recording is silent, or too quiet to hear.

A single file failing does not stop the rest. The summary at the
bottom counts how many worked and how many did not.


--------------------------------------------------------------------
 MOVING IT TO ANOTHER COMPUTER
--------------------------------------------------------------------

Copy the whole folder. The first run on the new computer offers to
install FFmpeg and uv, so there is nothing else to prepare.

If you would rather not install FFmpeg on every machine, put
"ffmpeg.exe" in a folder named "tools" beside "transcribe.bat" and
Mimir will use that copy instead, without asking to install anything.
