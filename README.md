# Mimir

Mimir turns recordings into text. Drop an audio file on it and a plain text
transcript appears next to that file. It can also read a document and answer a
question about it.

Everything runs from Windows Explorer: drag and drop, or a right-click menu
entry. There is no application to install and no interface to learn.

- **Transcribe** `.flac` `.m4a` `.mp3` `.mp4` `.mpeg` `.ogg` `.wav` `.webm`
- **Search** `.txt` `.docx` `.md`

---

## Table of contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running Mimir](#running-mimir)
- [Where the text goes](#where-the-text-goes)
- [The right-click menu](#the-right-click-menu)
- [Updating](#updating)
- [Uninstalling](#uninstalling)
- [Troubleshooting](#troubleshooting)
- [Moving Mimir to another computer](#moving-mimir-to-another-computer)
- [For developers](#for-developers)

---

## Requirements

| Requirement | Notes |
| --- | --- |
| Windows 10 or Windows 11 | Mimir is a set of `.bat` launchers and Python scripts; it does not run on macOS or Linux. |
| Windows App Installer (`winget`) | Ships with Windows. Used once to fetch FFmpeg and uv. |
| Internet connection | Needed for the first install and for every transcription. |
| An account on the transcription service | You supply the address and key. See [Configuration](#configuration). |

Mimir installs the rest for you:

| Installed by Mimir | What it is for |
| --- | --- |
| [FFmpeg](https://ffmpeg.org/) | Reads and splits the audio. |
| [uv](https://docs.astral.sh/uv/) | Runs the Python scripts and their dependencies. |
| Python 3.11+ | A private copy fetched by uv. Any Python already on the computer is left alone. |

No administrator rights are needed and nothing is written outside your own user
account.

---

## Installation

### 1. Get the folder

Download the repository as a ZIP and extract it, or clone it:

```bat
git clone https://github.com/stratusadv/Mimir.git
cd Mimir
```

Keep the folder together. The launchers find each other by relative path, so
copying out a single file will not work.

### 2. Run setup

Double-click `setup.bat`.

It checks the computer, installs anything missing, creates the `Mimir`
shortcut, and finishes with a report:

```
Everything Mimir needs:

  [ OK ] FFmpeg            reads the audio
  [ OK ] uv                runs the transcriber
  [ OK ] Python            a private copy, kept by uv
  [ OK ] Settings file     holds the service address and key
  [ OK ] Right-click menu  "Transcribe with Mimir" / "Search with Mimir"
```

If FFmpeg or uv is missing, Mimir lists it and asks:

```
[Y] Install   [N] Quit
```

Press `Y`. Windows may ask for permission — choose Yes. Occasionally Windows
needs the window closed and reopened before it notices the new programs; Mimir
says so, and you run it again.

Running `setup.bat` is optional. Mimir performs the same checks quietly every
time it starts, and only speaks up when something is missing.

Later on, `update.bat` fetches new releases. See [Updating](#updating).

### 3. Add the settings file

Setup cannot do this one step for you. See [Configuration](#configuration)
below.

### Offline or locked-down machines

If you would rather not install FFmpeg on every machine, put `ffmpeg.exe` in a
folder named `tools` inside `app` (`app\tools\ffmpeg.exe`, or
`app\tools\ffmpeg\bin\ffmpeg.exe`). Mimir uses that copy and never asks to
install anything.

---

## Configuration

Mimir reads its settings from a file named `.env` inside the `app` folder.

1. Copy `app\.env.example` to `app\.env`.
2. Fill in the address and key for your transcription service.

```ini
# Address of the transcription service, with no trailing slash.
AI_API_HOST=https://your-service-address

# Key for that service.
AI_API_KEY=your-key-here

# Model used for transcription.
LLM_AUDIO_MODEL=stratus.listen

# Model used for summarizing and search.
LLM_TEXT_MODEL=stratus.thinking
```

| Setting | Required | Used for |
| --- | --- | --- |
| `AI_API_HOST` | Yes | Base URL of the OpenAI-compatible service. No trailing slash. |
| `AI_API_KEY` | Yes | Credential for that service. |
| `LLM_AUDIO_MODEL` | No | Transcription model. Defaults to `stratus.listen`. |
| `LLM_TEXT_MODEL` | No | Notes, summaries, and document search. Defaults to `stratus.thinking`. |

> **Never commit or share `.env`.** It holds the account key. The file is
> already listed in `.gitignore`.

Any OpenAI-compatible endpoint works — Mimir talks to it through the `openai`
client with `base_url` pointed at `AI_API_HOST`.

---

## Running Mimir

### Transcribe audio

1. Find the `Mimir` shortcut in the folder — the one with the Mimir logo.
2. Drag an audio file, several audio files, or a whole folder onto it.
3. A window lists what it is about to transcribe and asks what you want:

   | Key | Result |
   | --- | --- |
   | `S` | A word-for-word transcript beside the audio (`_transcript.txt`). |
   | `N` | One notes file beside the audio (`_notes.txt`): summary, action items, and a tidied-up transcript. The raw transcript is not kept. |
   | `B` | Both files. |
   | `M` | Adds or removes the Windows right-click menu entry, then returns to this list. Nothing is transcribed. |
   | `Q` | Closes the window. Your files are left alone. |

   `N` and `B` take one extra AI pass, so they cost a little more and finish a
   little later.

4. Wait. A percentage counts up for each file. A one hour recording usually
   takes a couple of minutes.
5. When it finishes:

   | Key | Result |
   | --- | --- |
   | `T` | Opens the text that was just written (asks which, if there are several). |
   | `O` | Opens the containing folder with the first file selected. |
   | `R` | Returns to the output list to run the same files again with a different choice. |
   | `Q` | Closes the window. |

After `N` or `B`, Mimir asks what to search the notes for. Type a request in
plain language, or leave it blank to skip. If you type something, a
`SEARCH HIGHLIGHTS` section is added to the summary with the answer and quoted
passages.

You can also double-click the `Mimir` shortcut and type or paste a file path
when it asks. If the shortcut is missing, double-click `setup.bat` and it makes
a new one.

### Search a document

Right-click a `.txt`, `.docx`, or `.md` file and choose **Search with Mimir**.
Type what you want to find; Mimir reads the file, looks it up with AI, and shows
the answer in the window. Then it asks whether to write a `.txt` file beside the
original:

- `Y` writes `<name>_search.txt` next to the source file.
- `N` leaves the answer on screen only.

The original file is never changed.

### Running the scripts directly

The launchers are thin wrappers. If you prefer the command line:

```bat
:: transcribe: pass a text file holding one audio path per line
uv run --script app\audio_transcription.py <queue-file>

:: search: pass a text file holding one document path per line
uv run --script app\document_search.py <queue-file>
```

`uv` resolves the dependencies from the inline script metadata at the top of
each file, so no virtual environment or `pip install` step is needed.

---

## Where the text goes

Output is written beside the source file, never into a separate folder.

```
meeting notes.mp3   ->   meeting_notes_transcript.txt     (S or B)
meeting notes.mp3   ->   meeting_notes_notes.txt          (N or B)
meeting_notes_notes.txt  ->  meeting_notes_notes_search.txt   (document search)
```

Nothing is ever overwritten. If the name is taken, a number is added:

```
meeting_notes_transcript (1).txt
```

Each sentence is put on its own line, so the text is easy to skim and easy to
search.

The plain transcript is always written first, and the extra notes pass never
changes it. On `N` the transcript is deleted once the notes file is safely
written; if the notes pass fails, the transcript is kept and Mimir says so, so a
recording is never lost.

Anything that is not a supported file is ignored, and the window reports how
many files it skipped. One file failing does not stop the rest — the summary at
the bottom counts how many worked and how many did not.

> AI can make mistakes. Review the transcript before you rely on it.

---

## The right-click menu

Mimir can add itself to the Windows right-click menu, so you never have to go
looking for the shortcut. The first time you run it, Mimir asks:

```
Add Mimir to your right-click menu?
[Y] Add it   [N] No thanks
```

It only asks once. To change your mind later, run `setup.bat`, or run
`app\transcribe.bat` and press `M` at the main menu — that adds the entry if it
is missing and removes it if it is there.

Once it is on, **Transcribe with Mimir** appears when you right-click:

| You right-click | What happens |
| --- | --- |
| An audio file | Transcribes that file. |
| Several audio files | Transcribes all of them together. |
| A folder | Transcribes every audio file inside. |
| Empty space in a folder window | Opens Mimir for that folder. |
| The desktop | Opens Mimir and asks for a path. |

A `.txt`, `.docx`, or `.md` file gets **Search with Mimir** instead.

### What it actually changes

A handful of registry values under `HKEY_CURRENT_USER\Software\Classes`. That is
your account only: nothing is copied or installed anywhere else, no
administrator rights are needed, and removing the menu deletes exactly those
values and nothing else.

### Windows 11 and the short menu

Windows 11 shows a short right-click menu and hides everything else behind
**Show more options**. Mimir lives down there, because Windows only lets apps
installed from the Microsoft Store into the short menu.

The quickest way to reach Mimir is `Shift+F10` instead of a right-click — that
opens the long menu directly, with Mimir already in it.

Windows 11 can also be told to drop the short menu altogether and use the
full-length Windows 10 menu, which puts Mimir on the very first right-click. Run
`setup.bat` and choose "show Mimir in the first menu". Mimir never does this on
its own, and it asks again before changing anything. Worth knowing:

- It changes every right-click menu, not only Mimir's entry.
- Your account only. Nobody else on the computer is affected.
- The screen flickers once while Windows restarts the desktop, and open File
  Explorer windows close. Files and programs are untouched.
- Reversible: run `setup.bat` and choose to bring the short menu back.

---

## Updating

Double-click `update.bat`.

It asks GitHub what the newest release is, shows that next to the version you
have, and stops there if they match:

```
  Installed  v0.1
  Latest     v0.1

  [ OK ] Mimir is already up to date.
```

If there is a newer one, it says so and waits:

```
  Update Mimir to v0.2?

  [Y] Update   [N] Quit
```

Press `Y`. Mimir downloads the release, lays it over the folder, records the
new version, and re-runs the setup checks. It finishes with:

```
  [ OK ] Mimir is now v0.2.
```

The window closes partway through and a second one opens. That is normal:
`update.bat` cannot replace itself while it is running, so it hands the job to
a copy of itself in the temp folder.

### What is kept

| Kept | Replaced |
| --- | --- |
| `app\.env` — your address and key | Every file that came with Mimir |
| `mimir.log` | |
| `app\tools\` — your own FFmpeg copy | |
| The shortcut and the right-click menu | |

Changes you made to Mimir's own files are overwritten, so keep your own copies
elsewhere. Nothing in the folder is deleted: a file that a newer release no
longer ships is simply left behind.

The installed version is recorded in `app\version.txt`, and `setup.bat` prints
it at the bottom of its report. A folder installed before `update.bat` existed
has no such file; it reads as "not recorded", and updating writes one.

`update.bat /force` installs the latest release again even when the version
already matches, to repair a folder with missing or damaged files.

Nothing is downloaded until you press `Y`, and if the download fails or does
not look like Mimir, the folder is left untouched.

---

## Uninstalling

Double-click `uninstall.bat`.

It searches the computer first and shows what it found before it touches
anything:

```
  What was found:

    Mimir folders     2
      C:\Users\you\Desktop\audio_transciber
      C:\Users\you\Downloads\Mimir

    Registry entries  15   right-click menu and settings
    Shortcuts         1

  [Y] Remove all   [K] Keep folders   [D] Search more   [Q] Quit
```

`Y` deletes the folders and clears everything Mimir put in Windows. `K` clears
the Windows side but leaves the folders alone. `D` searches every fixed drive,
which is slower but finds a copy kept somewhere unusual. `Q` changes nothing.

The window closes partway through and a second one opens, for the same reason
`update.bat` does it: the script cannot delete the folder it is running from,
so it hands the job to a copy of itself in the temp folder.

### Why more than one copy matters

Every copy of Mimir writes the same right-click entries and the same shortcut
target, so the last one to run setup wins. A folder someone unzipped months ago
still answers to the same names, and after the newer copy is moved or renamed
the menu can end up pointing at the older one. `uninstall.bat` searches for all
of them rather than only the folder it sits in, which is what makes a clean
reinstall clean.

### What is removed

| Removed | Left alone |
| --- | --- |
| Every Mimir folder found, with `Y` | Transcripts and notes — they sit beside your audio files |
| `Transcribe with Mimir` and `Search with Mimir` menu entries, including any left by an older version | FFmpeg and uv, unless you ask for them |
| The `Mimir` shortcut, wherever it is | Everything else on the computer |
| `HKCU\Software\Mimir`, where the shortcut target and the menu answer are kept | |
| Leftover Mimir files in the temp folder | |

Before a folder is deleted, its `app\.env` is copied to
`%USERPROFILE%\Mimir-settings-backup`, so the address and key survive for a
future install.

Two extra questions come up only when they apply. If Mimir switched off the
Windows 11 short right-click menu, it offers to put that back. If FFmpeg and uv
are installed, it offers to remove them too — the safe answer is to leave them,
since they are ordinary tools and other programs may be using them. Removing uv
also clears the private Python and the download cache it keeps.

Menu entries written for every user on the machine, rather than just yours, need
administrator rights to clear. The report says so when that happens: right-click
`uninstall.bat`, choose "Run as administrator", and run it again.

`uninstall.bat /deep` starts with the every-drive search instead of offering it.

---

## Troubleshooting

Mimir keeps a log named `mimir.log` in the project folder. Every line is stamped
with the local date and time. If something fails and the window closes, that
file is the record of what happened.

| Message | Cause and fix |
| --- | --- |
| `FFmpeg did not install` / `uv did not install` | The install was cancelled, or there is no internet. Run `setup.bat` again. |
| `This computer is missing the Windows App Installer` | Open the Microsoft Store, search for "App Installer", install it, then try again. |
| `Python could not be set up` | uv could not download its private Python. Almost always a blocked or missing internet connection. |
| `setup.bat is missing from the Mimir folder` | Only part of Mimir was copied. Copy the whole folder. |
| `Missing settings file` | There is no `.env` in the `app` folder. See [Configuration](#configuration). |
| `No API settings were found` | The `.env` file exists but a line is blank or misspelled. |
| `ffmpeg could not read this file` | The recording is damaged, or the file is not really audio. |
| `the service returned no words for this audio` | The recording is silent, or too quiet to hear. |
| `Could not reach GitHub to ask what the latest version is` | `update.bat` has no internet, or GitHub is unreachable. Try again, or download the release by hand from the [releases page](https://github.com/stratusadv/Mimir/releases/latest). |
| `Some files could not be replaced` | A Mimir window was still open during an update. Close everything using the folder and run `update.bat` again. |
| The Mimir shortcut is gone or points nowhere | Double-click `setup.bat`. It remakes the shortcut wherever the folder now lives. |
| The right-click entry is missing or does nothing | The folder was moved or renamed. Run `setup.bat` and press `M` twice. |

---

## Moving Mimir to another computer

Copy the whole folder. Run `setup.bat` once on the new machine — that also makes
the shortcut there — or just use Mimir and let it sort itself out.

If you move the folder on the same machine, the old shortcut and right-click
entry still point at the old location. Run `setup.bat` from the new home, and
press `M` twice: once to remove the old entry, once to add it back.

---

## For developers

### Layout

```
Mimir/
├── setup.bat                       checks the machine, installs tools, makes the shortcut and menu
├── update.bat                      fetches the latest release and lays it over this folder
├── uninstall.bat                   finds every copy of Mimir and takes it off the computer
├── README.md                       this file
└── app/
    ├── .env                        your settings (git-ignored)
    ├── version.txt                 the release this folder came from
    ├── .env.example                template for the above
    ├── transcribe.bat              launcher for audio transcription
    ├── search.bat                  launcher for document search
    ├── audio_transcription.py      entry point: audio -> transcript / notes
    ├── document_search.py          entry point: document -> answer
    ├── transcription_manager.py    per-run orchestration and output naming
    ├── audio_file_transcriber.py   one audio file, end to end
    ├── audio_chunker.py            ffmpeg splitting into segments
    ├── transcription_client.py     audio model calls
    ├── transcript_polisher.py      cleanup, sections, summaries
    ├── document_searcher.py        chunked search and merge over a document
    ├── prompts.py                  model instructions
    ├── constants.py                limits, retries, supported extensions
    ├── data.py                     settings and result dataclasses
    ├── console.py                  window rendering
    ├── thread_pool.py              bounded worker pool
    ├── errors.py                   error types
    └── tests/                      sample audio fixtures
```

### Dependencies

Both entry points declare their dependencies with
[PEP 723](https://peps.python.org/pep-0723/) inline script metadata, and are run
with `uv run --script`. There is no `requirements.txt` and no virtual
environment to create.

| Script | Requires |
| --- | --- |
| `app/audio_transcription.py` | Python >= 3.11, `openai`, `python-dotenv` |
| `app/document_search.py` | Python >= 3.11, `openai`, `python-dotenv`, `python-docx` |

To add a dependency, edit the `# /// script` block at the top of the entry point
that needs it.

### How a transcription flows

1. `transcribe.bat` collects the dropped paths, checks the tooling, asks for an
   output mode, and writes a queue file.
2. `audio_transcription.py` loads `.env` into `TranscriptionSettings` and hands
   the queue to `TranscriptionManager`.
3. `AudioChunker` splits each file into fixed-length segments with FFmpeg.
4. `TranscriptionClient` sends the segments to `LLM_AUDIO_MODEL` through a
   bounded thread pool, retrying failed chunks.
5. The segments are joined, one sentence per line, and written beside the audio.
6. For `N` or `B`, `TranscriptPolisher` runs a second pass with
   `LLM_TEXT_MODEL` to produce the summary, action items, and cleaned
   transcript.

Document search follows the same shape through `document_search.py` and
`DocumentSearcher`, chunking the text, searching each chunk, and merging the
findings.

### Cutting a release

`update.bat` compares `app\version.txt` against the tag of the newest
published GitHub release, so both have to move together:

1. Put the new tag in `app\version.txt` (`v0.2`, matching the tag exactly).
2. Commit, tag the commit `v0.2`, and push the tag.
3. Publish a release for that tag. No attached files are needed — the update
   uses the source zip GitHub generates.

A release whose `app\version.txt` still holds the previous tag leaves everyone
who installs it being offered the same update again.

### Tuning

Retry counts, chunk length, worker limits, and supported extensions all live in
`app/constants.py`.

### Logging

Both entry points write to `mimir.log` in the project root (`LOG_PATH` in
`app/constants.py`). The log is git-ignored.
