# Changelog

## v2.2 (2026-11-19) - "Kabhi brain khatam nahi hota"
**Ek free brain khatam ho to agla free brain - automatically.**

New powers:
- **Groq chat brain** - the same free Groq key (console.groq.com, no card) that powers better Hindi Whisper hearing now also works as a fast fallback chat brain WITH tool use. Model configurable: `GROQ_MODEL=` (default llama-3.3-70b-versatile).
- **OpenCode brain** - if the free OpenCode CLI is installed, Jarvis falls back to its free models (default `opencode/deepseek-v4.1-flash-free`; free ids rotate - check `opencode models`, set `OPENCODE_MODEL=`). Privacy: saved memories/preferences are NOT sent to OpenCode, only the current chat. No tools in this mode - answers/advice only.
- **Free fallback chain** - Gemini -> Groq -> OpenCode -> Ollama (local, offline). Configurable via `BRAIN_CHAIN=` in `.env`. "brain mode groq karo" forces one brain; "brain status batao" shows which is active and which fallbacks are ready.
- Gemini free-limit handling now pauses Gemini for 30 minutes and walks the chain instead of giving up.

Already built-in (from earlier versions, still free): Groq Whisper hearing, edge-tts Hindi voice fallback (hi-IN-MadhurNeural, no key needed).

Engineering:
- 5 new offline tests (50 total): chain order, config defaults, new brain modes.
- Not verified on real Windows yet: live Groq chat calls, live OpenCode CLI runs (needs opencode installed + signed in there).

## v2.1 (2026-11-19) - "Insaan ki tarah kaam"
**Ek baar bolo, Jarvis step-by-step poora kaam karta hai - insaan ki tarah.**

New powers:
- **plan_and_do** - ek hi Hinglish sentence me poora kaam: "chrome kholke youtube pe Kesariya chalao", "google pe linux questions search karo aur notepad kholo", "whatsapp pe Rahul ko happy birthday bhejo aur enter daba do". Jarvis khud plan banata hai (brain se, ya offline parser se bina brain ke bhi), phir har step karta hai.
- **Har step HUD me dikhta hai** - comms log me "Step 1/3: Chrome khol raha hoon" jaisa live feedback.
- **WhatsApp contact se message** - number ya NAAM dono se: Jarvis WhatsApp Web kholkar chat dhundhta hai, message type karta hai aur Enter dabata hai. Naam wale flow me bhejne se pehle screen se verify karta hai ki sahi chat khuli (vision available ho to).
- **Message safety** - kisi ko message bhejne se pehle Jarvis recipient aur message padhkar sunata hai aur poochhta hai. "bina puche bhej do" bola ho to seedha bhejta hai. "mat bhejo, sirf likho" bola ho to type karke chhod deta hai.
- **"Ruk jao Jarvis"** - chalta hua plan turant rukta hai (voice ya type, dono se). PC ARMED/LOCKED switch pehle jaisa hi sab block karta hai.
- **Offline fallback parser** - brain (Gemini) limit pe ho ya net slow ho, common commands ka plan phir bhi banta hai.

Engineering:
- New `jarvis/agent.py` (planner + executor + WhatsApp flow), bus stop flag, main-loop stop interception, brain plan_text hook (Gemini, Ollama backup).
- 21 new offline tests (43 total): parser, JSON plans, dry-run executor, stop flag, WhatsApp confirm/auto-send rules.
- `JARVIS_DRY_RUN=true` (or non-Windows) = har step sirf list hota hai, kuch execute nahi - safe testing.

Not verified on real Windows yet: WhatsApp Web keyboard flow timings (page load waits), vision verification, mic flow. Akash ke laptop pe pehla run bataega.

## v2.0 (2026-11-19) - "Iron Man" polish
**Smarter, stronger, better tested.**

New powers:
- **Focus mode** - "25 minute focus mode": Jarvis stays quiet (no reminders/watchdog nudges) and announces when the session ends.
- **Clipboard history** - remembers the last 50 things you copied; "clipboard history dikhao" / "copy item 2".
- **Window snapping** - "Chrome ko left karo" / "VS Code maximize karo".
- **Webcam photo** - "photo kheencho" (always asks first).
- **Live currency** - "100 dollar kitne rupee" (free live rates).
- **Translate** - "translate karo Hindi me: good morning".
- **Internet speed test** - "speed test karo".
- **Big file finder** - "Downloads me badi files dikhao" to free disk space.
- **Reminders that survive restarts** - timers are saved to disk and re-armed when Jarvis starts; "reminders dikhao" / "reminder cancel karo".
- **Deep Jarvis voice by default** - Gemini voice "Alnilam" (change GEMINI_VOICE in .env: Achird, Algieba, Charon, Orus).

Fixes:
- Console/text mode no longer crashes (bus had no locked/mic_muted/info defaults without the HUD).
- PIN voice gate: "chrome kholo" no longer triggers a false PIN failure (unlock now needs the word "unlock"/"khol" as a full word).
- Voice gate with voiceprint mode but no voiceprint no longer raises an error.
- Model fallback chain tries stable Gemini models first.
- Reminder/focus timers are daemon threads (Jarvis exits cleanly).

Engineering:
- `tests/` - 22 offline tests (paths, yes/no, reminders, routines, clipboard, voice gate, tool registry).
- `run_tests.bat` + GitHub Actions CI (Windows + Linux).
- README rewritten with screenshots and honest limits.

## v1.7 and earlier
HUD with arc reactor, holographic boot, voice waveform; Gemini + Ollama dual brain with auto-switch; ~100 tools (apps, files, vision GUI control, winget installs, email, WhatsApp); morning briefing; dictation; meeting notes; website watch; usage report; watchdog; music; self-coding/self-healing/auto-update/skill learning; Google Calendar; Telegram phone remote; proactive agent; voice gate. (Versions 1.2-1.7, Oct 2026.)
