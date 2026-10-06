# JARVIS - your free PC assistant

Speak in Hindi/English mix. Jarvis listens, thinks, talks back, and controls your PC.
Everything here is FREE. No card. No plan. No payment.

## Setup (only once)

1. Install Python (free). Go to https://www.python.org/downloads/ , download it, open it.
   On the FIRST screen tick the box "Add Python to PATH", then click Install.
   (If Python is already installed, skip this.)
2. Unzip the Jarvis folder (right click -> Extract All).
3. Get your free Gemini key: open https://aistudio.google.com/apikey , login with Google,
   click "Create API key", copy it. No card needed.
4. Double-click `install.bat`. Wait 2-5 minutes. When it asks for the key, paste it
   (right-click in the window to paste) and press Enter.
5. Double-click `run.bat`. Jarvis says "Namaste". Now just speak!

If the key was not saved: open the file `.env` with Notepad, paste the key after `GEMINI_API_KEY=`, save.

## Every day
Double-click `run.bat`. To stop: say "bye Jarvis", or close the window.
Jarvis opens a dark window with a glowing circle. You can speak, or type in the box at the bottom.
No microphone? Just type in the box, or double-click `run_text.bat`.

## Things you can say
- "Chrome kholo" / "Notepad kholo" / "Calculator open karo"
- "YouTube pe Arijit Singh ka gaana chalao"
- "Google pe Linux interview questions search karo"
- "Downloads folder kholo" / "Desktop pe kya kya files hain?"
- "Mere PC me resume naam ki file dhundo"
- "Screenshot lo" / "Screen pe kya dikh raha hai?"
- "Volume badha do" / "Volume 40 kar do" / "Mute karo"
- "Battery kitni hai?" / "PC ki RAM kitni use ho rahi hai?"
- "10 minute baad yaad dilana ki paani peena hai"
- "Notepad kholo aur usme meri application likho"
- "Aaj ka mausam batao Mumbai ka"
- "Gmail kholo"

## Iron Man features (v1.2)
- Boot sequence + HUD: glowing reactor, voice visualizer bars, live CPU/RAM/disk/battery, comms log, quick buttons.
- Install software like a human: "VLC install karo", "Chrome install karo", "7zip uninstall karo". Jarvis searches with
  Windows winget (free, official), asks you, installs, then checks it really installed. If Windows shows an admin "Yes/No" box, click Yes yourself.
- Do things on screen like a human: "Settings me dark mode on karo", "installer me Next Next dabao". Jarvis looks at the screen,
  clicks and types step by step. Move the mouse into a screen corner to stop it instantly.
- Windows: "Chrome ko samne lao", "Notepad minimize karo", "desktop dikhao".
- News, Wikipedia, read a web page, notes, alarms, routines ("morning routine chalao", "study routine banao: chrome, youtube.com, notepad").
- Housekeeping: "Downloads folder arrange karo", "temp files saaf karo", "kaunsa program sabse zyada RAM le raha hai".
- Every action Jarvis takes is saved in `data/action_log.txt`.

## The HUD (v1.3)
Arc-reactor look like the Iron Man desktop: glowing blue ring, gauges (CPU/RAM/HDD/POWER), weather (set `WEATHER_CITY` in `.env`),
headlines, notes, quick links, comms log. Effects: holographic boot, orbiting particles, voice waveform ring, sliding panels,
task progress ring (fills while Jarvis works), screen-edge glow while listening.

## Self-upgrade and research (v1.3)
- Free offline brain: say "apne aap ko upgrade karo" (or "local brain setup karo"). Jarvis checks your PC (RAM/CPU/GPU/disk),
  picks a model that fits (small Llama for low RAM), asks you, installs Ollama (free), downloads the model, and turns on auto mode.
- Auto mode: Gemini first. When the Gemini free limit ends, Jarvis switches to the local brain by itself, then returns to Gemini after 30 minutes.
  Force a brain by voice: "brain ollama karo" / "brain gemini karo" / "brain auto karo". Ask "brain status".
- Local models are weaker, and weaker in Hindi, and they do not see the screen. It is a backup, not a replacement.
- Research mode: say "naye free tools dhundo" or "research karo voice assistants ke upgrades". Jarvis searches GitHub, Hacker News and the
  Ollama library and tells you ideas. It never installs anything without asking you.

## Big red switches
- HUD button "PC CONTROL: ARMED/LOCKED": click to LOCK. Jarvis then cannot touch your PC at all.
- "MIC: LIVE/MUTED" button turns off listening.

## Safety
Jarvis ALWAYS asks first ("haan" or "nahi") before: deleting files (they go to Recycle Bin), installing or removing programs, downloading files, taking over mouse/keyboard for a task,
shutdown/restart, closing apps, moving/overwriting files, running commands, sending email or WhatsApp.

## Better hearing (optional, free)
Default: Jarvis hears you using Gemini (same key, nothing extra).
For Whisper (more accurate Hindi): get a free key at https://console.groq.com/keys
(no card), paste in `.env` after `GROQ_API_KEY=`. Done - Jarvis uses it automatically.

## Voice
Jarvis speaks with the Gemini voice "Achird" (free, same key). Free Gemini voice has small limits, so when it is busy
Jarvis automatically switches to the free backup voice (Microsoft Hindi "Madhur") for 10 minutes, then tries Achird again.
In `.env`: `TTS_ENGINE=auto` (default), `gemini` (only Achird) or `edge` (only backup).
Backup voice: `VOICE=hi-IN-MadhurNeural` (male) or `VOICE=hi-IN-SwaraNeural` (female).

## Gmail read/send (optional, free)
Opening Gmail in browser works already. To let Jarvis read/send mail by voice:
1. Google Account -> Security -> turn on 2-Step Verification.
2. Search "App passwords" in your Google account, create one named Jarvis, copy the 16 letters.
3. In `.env` fill `GMAIL_ADDRESS=` and `GMAIL_APP_PASSWORD=`.

## Problems?
- "Gemini key galat": check the key in `.env`, no spaces.
- No voice heard: needs internet (voice is made online, free). Check speaker volume.
- Jarvis does not hear you: Windows Settings -> Privacy -> Microphone -> allow desktop apps. Set your mic as default.
- "Limit" message: free Gemini has a per-minute limit. Wait a minute.
- Say `WAKE_WORD_ENABLED=true` in `.env` if Jarvis reacts to TV/other voices; then start with "Jarvis ...".

## Limits (honest)
Free Gemini allows limited requests per minute/day. Jarvis controls the PC only while it is running.

## New in v1.4

**Feature Pack 2** (just ask by voice):
- "Good morning" / "morning briefing" - weather, news, notes, battery
- "Dictation shuru karo" - whatever you say is typed in the active app. Say "dictation band" to stop
- "Wo PDF dikhao jisme Linux commands the" - searches INSIDE your files (for PDF run: pip install pypdf, already in requirements)
- "Is website pe nazar rakho" - tells you when a page changes
- "Meeting mode start" / "meeting khatam" - notes saved in Documents/Jarvis-Meetings (it hears through the microphone, so keep the speaker on)
- "Aaj kitna time kis app me gaya" - usage report (tracking starts when Jarvis runs)
- PC watchdog - warns you about full disk, low battery, high RAM, heat
- "Arijit ka Tum Hi Ho chalao", "next", "pause" - hands-free music

**Self-improvement** (Jarvis NEVER changes itself without your yes):
- "Naya tool banao jo ..." - Jarvis writes new code, shows you, asks, saves a backup, then adds it
- "Apna bug fix karo" - reads data/errors.log, proposes a fix to one file, asks you, backs up, rolls back if it breaks
- "Update check karo" / "update karo" - new version from GitHub (private repo: put GITHUB_TOKEN in .env, or make the repo public)
- "Kaunse kaam baar-baar karta hoon?" - learns repeated tasks, offers a shortcut; "run skill NAME" replays it
- "Last change undo karo" - restores the backup. Everything is listed in data/changes.log ("change log dikhao")

## New in v1.5
- **Google Calendar**: "kal shaam 6 baje meeting add karo" opens Google Calendar with the event filled in, you press Save (no sign-in setup needed). To also READ your events, paste your calendar's secret iCal address in .env as GCAL_ICAL_URL.
- **Face greeting** (optional): set FACE_GREETING=true in .env. The webcam only checks if someone is in front of the PC and greets you when you come back after 20+ minutes. Local OpenCV, nothing is saved or uploaded.
- **Better memory**: Jarvis keeps a local database (data/memory.db) of your preferences and past chats. Say "yaad rakh, mujhe ... pasand hai" or "pichli baar maine kya kaam kiya tha?".
