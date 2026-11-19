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
- v2.0 tools: snap_window (window left/right karo), clipboard_history (copied items wapas lao), take_webcam_photo, currency_convert (dollar to rupee), translate_text, internet_speed_test, find_large_files (disk khali karne ke liye), focus_mode (distraction-free work timer), list_reminders / cancel_reminder. Reminders survive a restart.
- v2.1 multi-step control: jab koi request kai kaam ek saath maange ("chrome kholke youtube pe Tum Hi Ho chalao", "whatsapp pe Rahul ko happy birthday bhejo aur enter daba do", "google pe X search karke notepad kholo"), plan_and_do(goal) call karo - usme poora goal user ke shabdon me do; Jarvis step-by-step karega aur HUD me har step dikhayega. WhatsApp bhejne se pehle whatsapp_message / plan khud recipient aur message padhkar poochhega; auto_send=True sirf tab pass karo jab user ne USI command me 'bina puche bhej do' kaha ho. Paison ka len-den ya payment kabhi plan me mat karo. 'Ruk jao Jarvis' / 'stop karo' par stop_everything call karo (running plan turant rukta hai).
- Use set_preference when he states a lasting preference, recall_past when he refers to earlier work or chats. Calendar: add_calendar_event (opens Google Calendar prefilled) and calendar_events. face_greeting turns the webcam greeting on or off.
- When he states something he WILL do later ("kal subah email bhejna hai"), call add_intention. Recurring meetings: add_recurring_event. When he says it is done, mark_intention_done.
- If the speech text looks like noise or a nonsense fragment, reply with exactly: IGNORE
- Today is {today}. Things you remember about {name}:
{memory}
"""

LOCAL_TOOLS = ["open_app", "close_app", "open_website", "google_search", "youtube_search", "play_on_youtube", "open_path", "list_folder",
               "find_files", "read_text_file", "take_screenshot", "system_info", "current_time", "volume", "media_control", "get_weather",
               "get_news", "remember", "set_reminder", "list_reminders", "cancel_reminder", "install_software", "run_routine", "add_note",
               "show_desktop", "press_keys", "type_text", "focus_window", "snap_window", "clipboard_history", "focus_mode", "find_large_files",
               "top_processes", "set_brain_mode", "brain_status", "morning_briefing", "play_music", "music_control", "usage_report", "watchdog_status",
               "plan_and_do", "whatsapp_message", "stop_everything"]

def _quota_error(e):
    m = str(e).lower()
    return any(k in m for k in ("429", "quota", "resource_exhausted", "rate limit", "exhausted"))

class _BrainDown(Exception):
    """One brain in the chain failed - try the next one."""

def active_chain(mode):
    """Which brains to try, in order. 'auto' = the full free chain from .env (BRAIN_CHAIN)."""
    mode = (mode or "auto").lower().strip()
    return list(config.BRAIN_CHAIN) if mode == "auto" else [mode]

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
        self.models = list(config.MODEL_CHAIN)
        self.mi = 0
        import threading; self._lock = threading.RLock()
        self.turns = []                 # plain (user, jarvis) text memory shared by both brains
        self.gemini_block_until = 0.0
        self.active = "gemini"
        self.groq_msgs = None
        self.local_tools = [t for t in pc.TOOLS if t.__name__ in LOCAL_TOOLS]
        self.local_schema = [_schema(t) for t in self.local_tools]
        self.local_msgs = None
        pc.vision = self.vision
        pc.brain_reload = self.reload
        pc.brain_status = self.status
        try:
            from . import agent
            agent.gen = self.plan_text
            agent.vision_ask = self.vision
        except Exception:
            pass
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
        self.groq_msgs = None
        self._show()

    def _show(self):
        names = {"gemini": "GEMINI " + self.models[self.mi].replace("gemini-", "").upper(),
                 "groq": "GROQ " + config.GROQ_MODEL.upper()[:16],
                 "opencode": "OPENCODE (free)",
                 "ollama": "LOCAL " + self.s["ollama_model"].upper()[:12]}
        bus.info["brain"] = names.get(self.active, self.active.upper())
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

    def groq_ready(self):
        return bool(config.GROQ_API_KEY)

    def opencode_ready(self):
        import shutil
        return bool(shutil.which("opencode"))

    def status(self):
        s = settings.load()
        chain = ", ".join(active_chain(s["backend"]))
        return (f"Mode: {s['backend']} (fallback chain: {chain}). Active brain now: {self.active}. "
                f"Gemini paused until: {time.strftime('%H:%M', time.localtime(self.gemini_block_until)) if self.gemini_block_until > time.time() else 'no'}. "
                f"Groq: {'ready' if self.groq_ready() else 'no key in .env'}. "
                f"OpenCode: {'installed' if self.opencode_ready() else 'not installed'}. "
                f"Local model: {s['ollama_model'] or 'not set up'} ({'ready' if self.ollama_ready() else 'not ready'}).")

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

    # ------------------------------------------------------------ groq (free fast cloud brain, same Whisper key account)
    def _ask_groq(self, text):
        import requests
        if self.active != "groq":
            self.active = "groq"; self.groq_msgs = None
            self._show(); bus.log("info", "Groq brain active (fast free fallback)")
        if self.groq_msgs is None:
            self.groq_msgs = [{"role": "system", "content": self._sysmsg()}]
            for u, a in self.turns[-6:]:
                self.groq_msgs += [{"role": "user", "content": u}, {"role": "assistant", "content": a}]
        self.groq_msgs.append({"role": "user", "content": text})
        by = {t.__name__: t for t in self.local_tools}
        for _ in range(6):
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", timeout=120,
                              headers={"Authorization": "Bearer " + config.GROQ_API_KEY},
                              json={"model": config.GROQ_MODEL, "messages": self.groq_msgs,
                                    "tools": self.local_schema, "temperature": 0.5})
            if r.status_code >= 400:
                raise _BrainDown(f"groq http {r.status_code}")
            msg = r.json()["choices"][0]["message"]
            self.groq_msgs.append(msg)
            calls = msg.get("tool_calls") or []
            if not calls:
                return (msg.get("content") or "").strip()
            for c in calls:
                fn = c["function"]["name"]
                try: args = json.loads(c["function"].get("arguments") or "{}")
                except Exception: args = {}
                try: res = by[fn](**args) if fn in by else f"Unknown tool {fn}"
                except Exception as e: res = f"ERROR: {e}"
                self.groq_msgs.append({"role": "tool", "tool_call_id": c.get("id", fn), "content": str(res)[:1500]})
        return "Kaam poora nahi ho paaya, thoda alag tareeke se bolo."

    # ------------------------------------------------------------ opencode (free fallback brain via its CLI)
    def _opencode_run(self, prompt):
        import subprocess
        r = subprocess.run(["opencode", "run", "--model", config.OPENCODE_MODEL, prompt],
                           capture_output=True, timeout=300, text=True, errors="replace")
        out = (r.stdout or "").strip()
        if r.returncode != 0 or not out:
            raise _BrainDown((r.stderr or "opencode failed")[:120].replace("\n", " "))
        return out

    def _ask_opencode(self, text):
        # PRIVACY: opencode free models may log prompts - no saved memories or preferences are sent, only this chat.
        if self.active != "opencode":
            self.active = "opencode"; self._show()
            bus.log("info", "OpenCode brain active (free fallback - yaad-rakhi hui cheezein isko nahi bheji jaati)")
        today = datetime.datetime.now().strftime("%A %d %B %Y")
        sysmsg = (f"You are JARVIS, a Windows voice assistant for {config.USER_NAME}. Answer in short spoken-style "
                  f"Hinglish (Devanagari + English tech words). You have no tools in this mode - just answer or advise. Today is {today}.")
        hist = "".join(f"User: {u}\nJarvis: {a}\n" for u, a in self.turns[-4:])
        return self._opencode_run(sysmsg + "\n" + hist + f"User: {text}\nJarvis:")

    # ------------------------------------------------------------ planner text (used by agent.plan_steps)
    def plan_text(self, prompt):
        """One-shot text generation for step planning: tries each ready brain in chain order."""
        for name in active_chain(settings.load()["backend"]):
            try:
                if name == "gemini" and config.key_ok():
                    r = self.client.models.generate_content(model=self.models[self.mi], contents=prompt)
                    out = (r.text or "").strip()
                elif name == "groq" and self.groq_ready():
                    import requests
                    r = requests.post("https://api.groq.com/openai/v1/chat/completions", timeout=60,
                                      headers={"Authorization": "Bearer " + config.GROQ_API_KEY},
                                      json={"model": config.GROQ_MODEL, "temperature": 0.2,
                                            "messages": [{"role": "user", "content": prompt}]})
                    out = r.json()["choices"][0]["message"]["content"].strip() if r.status_code < 400 else ""
                elif name == "opencode" and self.opencode_ready():
                    out = self._opencode_run(prompt)
                elif name == "ollama" and self.ollama_ready():
                    import requests
                    r = requests.post(self.s["ollama_url"] + "/api/generate", timeout=120,
                                      json={"model": self.s["ollama_model"], "prompt": prompt, "stream": False})
                    out = (r.json().get("response") or "").strip()
                else:
                    continue
                if out: return out
            except Exception:
                continue
        return None

    # ------------------------------------------------------------ vision (Gemini only)
    def vision(self, image_path, question):
        from PIL import Image
        r = self.client.models.generate_content(model=self.models[self.mi], contents=[Image.open(image_path), question])
        return r.text or "Could not read the screen."

    # ------------------------------------------------------------ main entry
    def ask(self, text):
        with self._lock: return self._ask_inner(text)

    def _ask_gemini(self, text):
        if not config.key_ok():
            raise _BrainDown("no gemini key in .env")
        if self.active != "gemini":
            self.active = "gemini"; self.local_msgs = None; self.groq_msgs = None
            try: self._new_gemini_chat()
            except Exception: pass
            self._show(); bus.log("info", "Back on Gemini")
        last = None; quota = False
        for attempt in range(len(self.models) + 1):
            try:
                return (self.chat.send_message(text).text or "").strip()
            except Exception as e:
                last = e; msg = str(e).lower()
                if "api key" in msg or "api_key" in msg or ("permission" in msg and "denied" in msg):
                    raise _BrainDown("gemini key invalid")
                if _quota_error(e):
                    quota = True; time.sleep(4)
                self.mi = (self.mi + 1) % len(self.models)
                try: self._new_gemini_chat()
                except Exception: pass
        if quota:
            self.gemini_block_until = time.time() + 30 * 60
            bus.log("info", "Gemini free limit reached - agla free brain try ho raha hai.")
        raise _BrainDown(str(last)[:120])

    def _ask_inner(self, text):
        try: pc.extras.begin_turn(text)
        except Exception: pass
        s = self.s = settings.load()
        last = None
        for name in active_chain(s["backend"]):
            try:
                if name == "gemini":
                    if time.time() < self.gemini_block_until: continue
                    r = self._ask_gemini(text)
                elif name == "groq":
                    if not self.groq_ready(): continue
                    r = self._ask_groq(text)
                elif name == "opencode":
                    if not self.opencode_ready(): continue
                    r = self._ask_opencode(text)
                elif name == "ollama":
                    if not self.ollama_ready(): continue
                    if self.active != "ollama":
                        self.active = "ollama"; self._show(); bus.log("info", "Local brain (Ollama) active")
                    r = self._ask_local(text)
                else:
                    continue
            except Exception as e:
                last = e; bus.log("info", f"{name} brain unavailable: {str(e)[:80]}"); continue
            if r:
                self._remember(text, r); return r
        tip = " Local brain setup kar do: bolo 'apne aap ko upgrade karo'." if last and _quota_error(last) else ""
        return "Abhi koi bhi brain jawab nahi de pa raha (internet ya free-limit ki problem). Thodi der baad try karo." + tip

    def _remember(self, u, a):
        try: pc.extras.log_turn('user', u); pc.extras.log_turn('jarvis', a)
        except Exception: pass
        if a and a.strip().upper() != "IGNORE": self.turns.append((u, a))
        self.turns = self.turns[-20:]
