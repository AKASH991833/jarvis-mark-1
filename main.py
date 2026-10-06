import sys, re, time, argparse, threading, queue
from jarvis import config, pc, bus

YES = ("yes", "yeah", "yep", "haan", "han", "ha", "kar do", "karo", "kardo", "theek", "thik", "ok", "okay", "sure", "bilkul", "ji", "हाँ", "हां", "हा", "जी", "करो", "कर दो", "ठीक", "बिल्कुल", "ओके")
NO = ("no", "nahi", "nahin", "nai", "mat", "ruko", "ruk", "cancel", "stop", "नहीं", "नही", "मत", "रुको", "रुक", "कैंसल")

def has(words, s):
    return any(re.search(r"(^|\W)" + re.escape(w) + r"(\W|$)", s) for w in words)

def assistant(text_mode, typed):
    """typed = queue of typed lines (from window) or None for plain console."""
    from jarvis.brain import Brain
    from jarvis.speak import speak, set_client
    brain = Brain(); set_client(brain.client)
    if not text_mode:
        from jarvis import listen

    def hear(wait=3.0):
        if typed is not None:
            try: return typed.get_nowait()
            except queue.Empty: pass
        if text_mode:
            if typed is not None:
                time.sleep(0.3); return ""
            try: return input(f"\033[92m{config.USER_NAME}:\033[0m ").strip()
            except EOFError: return "bye jarvis"
        if bus.mic_muted:
            time.sleep(0.4); return ""
        bus.state("listening")
        wav = listen.record(max_wait=wait)
        bus.state("idle")
        if not wav: return ""
        bus.state("thinking")
        t = listen.transcribe(wav, brain.client)
        if t: bus.log("user", t)
        return t

    def confirm(question):
        for _ in range(2):
            speak(question)
            end = time.time() + 12; ans = ""
            while time.time() < end and not ans:
                ans = hear(4.0)
            ans = ans.lower().strip()
            if has(NO, ans): return False
            if has(YES, ans): return True
            speak("Mujhe samajh nahi aaya. Haan ya nahi bolo.")
        return False

    pc.confirm = confirm
    try: pc.extras.start_background()
    except Exception: pass
    pc.notify = lambda t: speak(t)
    bus.info["model"] = config.GEMINI_MODEL
    h = time.localtime().tm_hour
    wish = "Suprabhat" if h < 12 else ("Namaste" if h < 17 else "Shubh sandhya")
    extra = ""
    try:
        import psutil
        b = psutil.sensors_battery()
        if b: extra = f" Battery {int(b.percent)} percent hai."
    except Exception: pass
    speak(f"{wish} {config.USER_NAME}. Saari systems online hain.{extra} Bolo, kya karna hai?")
    while True:
        t = hear()
        if not t: continue
        low = t.lower()
        if config.WAKE_WORD_ENABLED and not text_mode and typed is None and not any(w in low for w in (config.WAKE_WORD, "जार्विस", "जर्विस")):
            continue
        if re.search(r"\b(bye jarvis|goodbye|alvida)\b", low) or "अलविदा" in t or "बाय जार्विस" in t:
            speak("Theek hai, phir milte hain. Bye!"); return
        bus.state("thinking")
        reply = brain.ask(t)
        if reply and reply.strip().upper() != "IGNORE": speak(reply)
        else: bus.state("idle")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", action="store_true", help="typed mode only"); ap.add_argument("--console", action="store_true", help="no window")
    a = ap.parse_args()
    if not config.key_ok():
        print("\nGemini key missing! Open the file named .env with Notepad and paste your key after GEMINI_API_KEY=\nGet free key: https://aistudio.google.com/apikey\n")
        input("Press Enter to close..."); return
    if a.console:
        try: assistant(a.text, None)
        except KeyboardInterrupt: print("\nBye!")
        return
    try:
        from jarvis.ui import App
        app = App(n_tools=len(pc.TOOLS))
    except Exception as e:
        print(f"[window not available ({e}), using console]")
        try: assistant(a.text, None)
        except KeyboardInterrupt: print("\nBye!")
        return
    def work():
        try: assistant(a.text, app.typed)
        except Exception as e: bus.log("info", f"Error: {e}")
        app.root.after(1500, app.root.destroy)
    app.on_ready = lambda: threading.Thread(target=work, daemon=True).start()
    app.run()

if __name__ == "__main__":
    main()
