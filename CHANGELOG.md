# Changelog

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
