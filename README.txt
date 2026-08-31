====================================================================
 MIMIR - AUDIO TO TEXT
====================================================================

Mimir turns recordings into text files. Drop an audio file on it and
a plain text transcript appears right next to that file.


--------------------------------------------------------------------
 WHAT IS IN THIS FOLDER
--------------------------------------------------------------------

    Mimir             the one you use. Drop audio on it, or
                      double-click it. It is a shortcut with the
                      Mimir logo, made by setup.bat.
    setup.bat         gets the computer ready. Run it once, or never
                      - Mimir runs it for you.
    README.txt        this file.
    app               the machinery, and the .env settings file.

Everything inside "app" looks after itself. Leave it alone, apart
from the .env file described under FIRST TIME SETUP.


--------------------------------------------------------------------
 HOW TO USE IT
--------------------------------------------------------------------

1. Find "Mimir" in this folder - the shortcut with the Mimir
   logo on it.

2. Drag your audio file (or a whole folder of them) on top of the
   Mimir shortcut and let go.

3. A black window opens and lists what it is about to transcribe.
   Press S to start, Q to quit, or M to manage the right-click menu.

4. Wait. A percentage counts up for each file. A one hour recording
   usually takes a couple of minutes.

5. When it finishes you can press O to open the folder with your new
   transcript in it, R to transcribe something else, or Q to close.

You can also just double-click the Mimir shortcut and type or paste
a file path when it asks.

If the Mimir shortcut is not there, double-click "setup.bat" once and
it makes a new one.

Better still, let Mimir add itself to your right-click menu the first
time it runs - see THE RIGHT-CLICK MENU below. After that you can
right-click any audio file, anywhere, and pick "Transcribe with
Mimir" without opening this folder at all.


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

There is nothing to install by hand, and nothing you have to run
first. Every time Mimir starts it quietly checks the computer, and
only speaks up if something is missing.

If you would rather see the whole picture, double-click "setup.bat".
It checks everything, fixes what it can, and finishes with a report:

    Everything Mimir needs:

      [ OK ] FFmpeg            reads the audio
      [ OK ] uv                runs the transcriber
      [ OK ] Python            a private copy, kept by uv
      [ OK ] Settings file     holds the service address and key
      [ OK ] Right-click menu  "Transcribe with Mimir"

WHAT IT INSTALLS
    FFmpeg and uv are two small free programs, installed once per
    computer through the App Installer that comes with Windows. If
    either is missing Mimir lists it and asks:

        Install them now? [Y] yes   [N] quit

    Press Y. Windows may pop up a box asking for permission - choose
    Yes. Very occasionally Windows needs the window closed and
    reopened before it notices the new programs. Mimir says so if
    that happens, and you just run it again.

    Python is handled separately. Mimir does not use, change, or
    care about any Python already on the computer - uv fetches a
    private copy that belongs to Mimir alone.

THE ONE THING SETUP CANNOT DO
    There must be a file called ".env" sitting inside the "app"
    folder. It holds the address and key for the transcription
    service:

        AI_API_KEY=your-key-here
        AI_API_HOST=https://your-service-address
        LLM_AUDIO_MODEL=stratus.listen

    Setup will tell you if it is missing, but it cannot invent one.
    Do not share that file and do not put it on the internet. It is
    the key to the account.


--------------------------------------------------------------------
 THE RIGHT-CLICK MENU
--------------------------------------------------------------------

Mimir can put itself into the Windows right-click menu, so you never
have to go looking for the Mimir shortcut again.

The first time you run it, Mimir asks:

    Add Mimir to your right-click menu?
    Add it? [Y] yes   [N] no thanks

Press Y and it sets itself up. It only asks once. To change your mind
later, run setup.bat, or run transcribe.bat and press M at the main
menu - that adds it if it is missing and removes it if it is there.

Once it is on, you get "Transcribe with Mimir" when you right-click:

    an audio file          transcribes that file
    several audio files    transcribes all of them together
    a folder               transcribes every audio file inside
    empty space in a       opens Mimir for that folder
      folder window
    the desktop            opens Mimir and asks for a path

The Mimir logo appears beside the menu entry.

WINDOWS 11 AND THE SHORT MENU
    Windows 11 shows a short right-click menu and hides everything
    else behind "Show more options" at the bottom. Mimir lives down
    there, because Windows only lets apps installed from the
    Microsoft Store into the short menu. No script can put itself
    there.

    The quickest way to reach Mimir is Shift+F10 instead of a
    right-click - that opens the long menu directly, with Mimir
    already in it.

    There is one other way, and Mimir will never do it unless you go
    looking for it. Windows 11 can be told to drop the short menu
    altogether and use the full-length menu Windows 10 had, which
    puts Mimir on the very first right-click. To do that, run
    setup.bat and choose "show Mimir in the first menu". It explains
    itself and asks again before changing anything.

    Worth knowing if you are considering it:

      - It changes every right-click menu, not only Mimir.
      - Your account only. Nobody else on the computer is affected,
        and no administrator rights are needed.
      - The screen flickers once while Windows restarts the desktop,
        and open File Explorer windows close. Files and programs are
        untouched.
      - Reversible. Run setup.bat and choose to bring the short menu
        back.

    Mimir never suggests this on its own, and installing the
    right-click entry does not change your menu style.

WHAT IT ACTUALLY CHANGES
    A handful of registry values under
    HKEY_CURRENT_USER\Software\Classes. That is your account only:
    nothing is copied or installed anywhere, and removing the menu
    deletes exactly those values and nothing else.

IF YOU MOVE THE MIMIR FOLDER
    The menu entry remembers where the folder was. After moving it,
    run setup.bat from its new home and press M twice - once to
    remove the old entry, once to add it back pointing at the new
    location. Running setup.bat also repairs the Mimir shortcut,
    which remembers the old place in the same way.


--------------------------------------------------------------------
 IF SOMETHING GOES WRONG
--------------------------------------------------------------------

"FFmpeg did not install" or "uv did not install"
    The install was cancelled, or the computer has no internet. Try
    running setup.bat again.

"This computer is missing the Windows App Installer"
    Mimir cannot install anything without it. Open the Microsoft
    Store, search for "App Installer", install it, and try again.

"Python could not be set up"
    Mimir could not download its private copy of Python. Almost
    always a blocked or missing internet connection.

"setup.bat is missing from the Mimir folder"
    Only part of Mimir was copied. Copy the whole folder.

The Mimir shortcut is gone, or says it cannot find what it points to
    Double-click setup.bat. It makes the shortcut again, pointing at
    wherever the folder now lives.

The right-click entry is missing, or does nothing
    The Mimir folder was probably moved or renamed. Run setup.bat and
    press M twice to point it at the new place.

"Missing settings file"
    The .env file is not in the "app" folder. Copy the whole Mimir
    folder, not just the shortcut.

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

Copy the whole folder. Run setup.bat once on the new machine - that
also makes the Mimir shortcut there - or just use Mimir and let it
sort itself out.

If you would rather not install FFmpeg on every machine, put
"ffmpeg.exe" in a folder named "tools" inside the "app" folder, and
Mimir will use that copy instead, without asking to install anything.
