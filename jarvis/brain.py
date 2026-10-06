"""Two brains in one: Gemini (free tier, cloud) and Ollama (free, local, offline).
auto = Gemini first; when Gemini free quota ends and a local model is ready, switch to Ollama, and come back to Gemini later."""
import time, inspect, datetime, json
from . import config, pc, bus, settings

SYSTEM = """You are JARVIS, the personal voice assistant living inside {name}'s Windows PC. You can control the whole PC with your tools (files, apps, browser, keyboard, mouse, screen, shell, email, software install).
RULES:
- {name} speaks Hinglish (Hindi + English mix). Reply in simple, friendly Hindi written in Devanagari script, keeping common English tech words (Chrome, folder, file, YouTube) in English. If he talks in pure English, reply in English.
- Replies are spoken aloud: keep them SHORT (1-3 sentences). No markdown, no bullet symbols, no emojis, no URLs read out.
- When he asks for an action, DO it with a tool right away. Do not ask unnecessary questions. Guess sensible defaults (Downloads folder, Chrome browser).
- For several steps, call tools one after another until the job is finished, then say what you did. If something fails, try another way (different tool or gui_task) before giving up, and verify the result.
- Dangerous tools (delete, shutdown, install, shell commands, email, WhatsApp) ask {name} for permission themselves. Never pretend you did something you did not; if a tool returns an error, say so simply.
- Never install, download or change anything on your own initiative from research or suggestions: only suggest, and let {name} decide.
- Morning briefing: call morning_briefing and read it out as a short friendly summary. Dictation, meeting notes, website watch, file content search, usage report, PC health and music all have tools. Self-improvement tools (create_new_tool, self_heal, apply_update, save_skill, undo_last_change) always ask {name} for a yes themselves; never call them unless he asked or agreed.
- Use set_preference when he states a lasting preference, recall_past when he refers to earlier work or chats. Calendar: add_calendar_event (opens Google Calendar prefilled) and calendar_events. face_greeting turns the webcam greeting on or off.
- When he states something he WILL do later ("kal subah email bhejna hai"), call add_intention. Recurring meetings: add_recurring_event. When he says it is done, mark_intention_done.
- If the speech text looks like noise or a nonsense fragment, reply with exactly: IGNORE
- Today is {today}. Things you remember about {name}:
{memory}
"""

LOCAL_TOOLS = ["open_app", "close_app", "open_website", "google_search", "youtube_search", "play_on_youtube", "open_path", "list_folder",
               "find_files", "read_text_file", "take_screenshot", "system_info", "current_time", "volume", "media_control", "get_weather",
               "get_news", "remember", "set_reminder", "install_software", "run_routine", "add_note", "show_desktop", "press_keys", "type_text",
               "focus_window", "top_processes", "set_brain_mode", "brain_status", "morning_briefing", "play_music", "music_control", "usage_report", "watchdog_status"]

def _quota_error(e):
    m = str(e).lower()
    return any(k in m for k in ("429", "quota", "resource_exhausted", "rate limit", "exhausted"))

def _schema(fn):
    props, req = {}, []
    for n, p in inspect.signature(fn).parameters.items():
        ann = p.annotation
        ty = {int: "integer", float: "number", bool: "boolean"}.get(ann, "string")
        props[n] = {"type": ty}
        if p.default is inspect._empty: req.append(n)
    doc = (fn.__doc__ or "").strip().split("\n")[0][:160]
    return {"type": "function", "function": {"name": fn.__name__, "description": doc,
            "parameters": {"type": "object", "properties": props, "required": req}}}

class Brain:
    def __init__(self):
        from google import genai
        from google.genai import types
        self.genai, self.types = genai, types
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.models = list(dict.fromkeys([config.GEMINI_MODEL, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]))
        self.mi = 0
        import threading; self._lock = threading.RLock()
        self.turns = []                 # plain (user, jarvis) text memory shared by both brains
        self.gemini_block_until = 0.0
        self.active = "gemini"
        self.local_tools = [t for t in pc.TOOLS if t.__name__ in LOCAL_TOOLS]
        self.local_schema = [_schema(t) for t in self.local_tools]
        self.local_msgs = None
        pc.vision = self.vision
        pc.brain_reload = self.reload
        pc.brain_status = self.status
        self.reload()

    # ------------------------------------------------------------ setup
    def _sysmsg(self):
        return SYSTEM.format(name=config.USER_NAME, today=datetime.datetime.now().strftime("%A %d %B %Y %I:%M %p"),
                             memory=(pc.load_memory() or "(nothing yet)") + " | Saved preferences: " + (pc.extras._prefs_text() or "none"))

    def _history(self):
        out = []
        for u, a in self.turns[-8:]:
            out.append(self.types.Content(role="user", parts=[self.types.Part(text=u)]))
            out.append(self.types.Content(role="model", parts=[self.types.Part(text=a)]))
        return out

    def _new_gemini_chat(self):
        cfg = self.types.GenerateContentConfig(system_instruction=self._sysmsg(), tools=pc.TOOLS, temperature=0.6)
        self.chat = self.client.chats.create(model=self.models[self.mi], config=cfg, history=self._history())

    def reload(self):
        self.s = settings.load()
        try: self._new_gemini_chat()
        except Exception as e: print("[brain setup]", e)
        self.local_msgs = None
        self._show()

    def _show(self):
        bus.info["brain"] = ("LOCAL " + self.s["ollama_model"].upper()[:12]) if self.active == "ollama" else ("GEMINI " + self.models[self.mi].replace("gemini-", "").upper())
        bus.info["model"] = bus.info["brain"]

    # ------------------------------------------------------------ local (Ollama)
    def ollama_ready(self):
        import requests
        m = self.s.get("ollama_model")
        if not m: return False
        try:
            tags = requests.get(self.s["ollama_url"] + "/api/tags", timeout=3).json().get("models", [])
            return any(t["name"].split(":")[0] == m.split(":")[0] and (":" not in m or t["name"] == m or t["name"].startswith(m)) for t in tags)
        except Exception:
            return False

    def status(self):
        s = settings.load()
        return (f"Mode: {s['backend']}. Active brain now: {self.active} "
                f"({'Gemini ' + self.models[self.mi] if self.active == 'gemini' else 'Ollama ' + s['ollama_model']}). "
                f"Local model: {s['ollama_model'] or 'not set up'} ({'ready' if self.ollama_ready() else 'not ready'}). "
                f"Gemini paused until: {time.strftime('%H:%M', time.localtime(self.gemini_block_until)) if self.gemini_block_until > time.time() else 'no'}.")

    def _ask_local(self, text):
        import requests
        if self.local_msgs is None:
            self.local_msgs = [{"role": "system", "content": self._sysmsg() + "\nYou are running on a small local model: be brief and use tools when asked."}]
            for u, a in self.turns[-6:]:
                self.local_msgs += [{"role": "user", "content": u}, {"role": "assistant", "content": a}]
        self.local_msgs.append({"role": "user", "content": text})
        by = {t.__name__: t for t in self.local_tools}
        for _ in range(6):
            r = requests.post(self.s["ollama_url"] + "/api/chat", timeout=300, json={
                "model": self.s["ollama_model"], "messages": self.local_msgs, "tools": self.local_schema, "stream": False,
                "options": {"num_ctx": 4096, "temperature": 0.4}})
            r.raise_for_status()
            msg = r.json()["message"]
            self.local_msgs.append(msg)
            calls = msg.get("tool_calls") or []
            if not calls:
                return (msg.get("content") or "").strip()
            for c in calls:
                fn = c["function"]["name"]; args = c["function"].get("arguments") or {}
                try: res = by[fn](**args) if fn in by else f"Unknown tool {fn}"
                except Exception as e: res = f"ERROR: {e}"
                self.local_msgs.append({"role": "tool", "tool_name": fn, "content": str(res)[:1500]})
        return "Kaam poora nahi ho paaya, thoda alag tareeke se bolo."

    # ------------------------------------------------------------ vision (Gemini only)
    def vision(self, image_path, question):
        from PIL import Image
        r = self.client.models.generate_content(model=self.models[self.mi], contents=[Image.open(image_path), question])
        return r.text or "Could not read the screen."

    # ------------------------------------------------------------ main entry
    def ask(self, text):
        with self._lock: return self._ask_inner(text)

    def _ask_inner(self, text):
        try: pc.extras.begin_turn(text)
        except Exception: pass
        s = self.s = settings.load()
        mode = s["backend"]
        use_local = mode == "ollama" or (mode == "auto" and time.time() < self.gemini_block_until)
        if use_local and self.ollama_ready():
            if self.active != "ollama":
                self.active = "ollama"; self._show(); bus.log("info", "Local brain (Ollama) active")
            try:
                r = self._ask_local(text); self._remember(text, r); return r
            except Exception as e:
                bus.log("info", f"Local brain problem: {str(e)[:100]}")
                if mode == "ollama": return "Local model me problem aayi. Ollama chal raha hai ya nahi check karo."
        if self.active != "gemini":
            self.active = "gemini"; self.local_msgs = None
            try: self._new_gemini_chat()
            except Exception: pass
            self._show(); bus.log("info", "Back on Gemini")
        last = None
        for attempt in range(len(self.models) + 1):
            try:
                r = (self.chat.send_message(text).text or "").strip()
                self._remember(text, r); return r
            except Exception as e:
                last = e; msg = str(e).lower()
                if "api key" in msg or "api_key" in msg or ("permission" in msg and "denied" in msg):
                    return "Mujhe lagta hai Gemini key galat hai. .env file me key check karo."
                if _quota_error(e):
                    if mode == "auto" and self.ollama_ready():
                        self.gemini_block_until = time.time() + 30 * 60
                        bus.log("info", "Gemini free limit reached. Switching to local brain for 30 minutes.")
                        return self._ask_inner(text)
                    time.sleep(4)
                self.mi = (self.mi + 1) % len(self.models)
                try: self._new_gemini_chat(); self._show()
                except Exception: pass
        print(f"[brain error: {last}]")
        tip = " Local brain setup kar do: bolo 'apne aap ko upgrade karo'." if _quota_error(last) else ""
        return "Abhi internet ya Gemini limit ki problem hai. Thodi der baad try karo." + tip

    def _remember(self, u, a):
        try: pc.extras.log_turn('user', u); pc.extras.log_turn('jarvis', a)
        except Exception: pass
        if a and a.strip().upper() != "IGNORE": self.turns.append((u, a))
        self.turns = self.turns[-20:]
