# Changelog

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
