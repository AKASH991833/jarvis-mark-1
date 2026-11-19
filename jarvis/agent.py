"""v2.1 - Jarvis does chained jobs like a human at the PC.

One Hinglish sentence becomes a small step plan, then Jarvis runs it step by step,
showing every step in the HUD log. "Ruk jao Jarvis" stops it between steps.

Two ways a plan is made:
1. The active brain (Gemini, or local Ollama) writes a JSON plan (agent.gen hook).
2. A built-in offline Hinglish parser (parse_steps_local) - always available,
   covers the common commands even when the brain is unreachable.

Everything is DRY-RUN safe: on non-Windows, or when JARVIS_DRY_RUN=true, steps are
only listed, never executed - used by the offline tests.
"""
import os, re, sys, json, time
from . import bus

IS_WIN = sys.platform.startswith("win")

def _env_on(name):
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "y", "on")

# On Windows do real actions; anywhere else (dev/CI) only print what would happen.
DRY_RUN = _env_on("JARVIS_DRY_RUN") or not IS_WIN

# hooks, set by Brain
gen = lambda prompt: None            # prompt -> plan JSON text, or None
vision_ask = lambda image_path, question: ""  # screenshot question answering

ACTIONS = ("open_app", "open_url", "play_youtube", "search_google", "whatsapp",
           "type", "key", "click", "wait")

PLAN_PROMPT = """You are the planner inside JARVIS, a Windows voice assistant. Turn the user's Hinglish request into a short JSON list of steps that control the PC like a human.

Allowed steps (use ONLY these "action" values):
- {"action":"open_app","name":"chrome"} - open an app
- {"action":"open_url","url":"https://..."} - open a website in the browser
- {"action":"play_youtube","query":"song name"} - find and play a song/video on YouTube
- {"action":"search_google","query":"..."} - Google search in the browser
- {"action":"whatsapp","contact":"name or phone with country code","message":"text","send":true} - open WhatsApp, find the chat, type the message; send:true also presses Enter
- {"action":"type","text":"..."} - type into the focused window
- {"action":"key","keys":"enter"} - press a key or shortcut like enter, ctrl+s, alt+tab
- {"action":"click","what":"the Next button"} - find a visible button/link by description and click it
- {"action":"wait","seconds":3} - pause (max 120)

Rules:
- Reply with ONLY the JSON list, no explanation, no markdown fences.
- Keep it minimal: 1-8 steps. Add a short wait after opening apps/sites that need loading.
- For WhatsApp: send:true ONLY if the user clearly wants the message sent ("bhej do", "send karo", "enter daba do"); otherwise send:false so the message stays typed for him to review.
- Never plan purchases, payments, deletions or password entry. If the request needs one, reply [] instead.

Request: {goal}
"""

STOP_PHRASES = ("ruk jao", "ruk ja", "stop karo", "stop kar", "band karo jo kar raha", "bas karo", "cancel karo jo kar raha",
                "रुक जाओ", "रुक जा", "बस करो", "स्टॉप")

def request_stop():
    bus.stop = True

def clear_stop():
    bus.stop = False

def _stopped():
    return getattr(bus, "stop", False)

def _log(text):
    bus.log("step", text)

# ---------------------------------------------------------------- WhatsApp Web flow (free, keyboard-driven)
def _wa_send_flow(contact_or_phone, message, send):
    """Real WhatsApp Web automation (Windows only). Returns a status string."""
    from . import pc
    import pyautogui, urllib.parse, webbrowser
    raw = contact_or_phone.strip()
    digits = re.sub(r"\D", "", raw)
    is_phone = bool(re.fullmatch(r"[\d+\s()\-]+", raw)) and len(digits) >= 10
    if is_phone:
        if raw.startswith("+") or len(digits) > 10:
            phone = digits
        else:
            phone = "91" + digits  # default India
        url = "https://web.whatsapp.com/send?phone=" + phone
        if message:
            url += "&text=" + urllib.parse.quote(message)
        webbrowser.open(url)
        _log("WhatsApp Web khul raha hai (chat: " + phone + ") ...")
        _wait(15)
        if _stopped(): return "Stopped before sending."
        if send:
            pyautogui.press("enter")
            _log("Enter daba diya - message bhej diya.")
            return "WhatsApp message sent to " + phone + " (if WhatsApp Web was logged in)."
        return "Chat khul gayi, message box me likha hua hai - aap khud Enter daba sakte ho."
    # contact by NAME: search flow
    webbrowser.open("https://web.whatsapp.com/")
    _log("WhatsApp Web khul raha hai, '" + raw + "' dhundh raha hoon ...")
    _wait(14)
    if _stopped(): return "Stopped."
    pyautogui.hotkey("ctrl", "alt", "/")   # WhatsApp Web search-box shortcut
    time.sleep(1.0)
    pc.type_text(raw)
    time.sleep(2.5)
    pyautogui.press("enter")               # open the top matching chat
    time.sleep(1.5)
    if _stopped(): return "Stopped."
    if send:
        try:  # best-effort safety: confirm the open chat really is the asked contact
            import tempfile
            shot = os.path.join(tempfile.gettempdir(), "jarvis_wa.png")
            pyautogui.screenshot().save(shot)
            ans = (vision_ask(shot, "WhatsApp Web is open. Reply in ONE short line: the NAME of the chat currently open, or 'none' if no chat is open.") or "").lower()
            first = raw.split()[0].lower()
            if ans and "none" not in ans and first not in ans:
                return f"Ruk gayi: open chat '{ans.strip()[:40]}' lag raha hai, '{raw}' nahi. Kuch bheja nahi gaya - chat khuli hai, aap khud dekh lo."
        except Exception:
            pass  # vision unavailable: continue, the user already confirmed recipient + text
    if message:
        pc.type_text(message)
        time.sleep(0.4)
    if send:
        if _stopped(): return "Stopped before sending."
        pyautogui.press("enter")
        _log("Enter daba diya - message bhej diya.")
        return "WhatsApp message bhej diya: " + raw
    return "'" + raw + "' ki chat kholkar message type kar diya hai. Enter aap dabao, ya bolo 'enter daba do'."

def whatsapp_message(contact_or_phone: str, message: str, send: bool = True, auto_send: bool = False) -> str:
    """Open WhatsApp (Web), find a chat by NAME or PHONE, type a message and press Enter. send=True sends it; send=False only types it so the user can check. Always reads back recipient + message and asks first, UNLESS the user's own command said 'bina puche bhej do' (then pass auto_send=True)."""
    from . import pc
    if send and not auto_send:
        if not pc.confirm(f"WhatsApp pe {contact_or_phone} ko ye message bhejun: '{message[:120]}'. Bhej doon?"):
            return "User said no. Message nahi bheja."
    if DRY_RUN:
        return (f"[DRY RUN] WhatsApp -> {contact_or_phone}: '{message}' "
                + ("+ Enter (send)" if send else "(typed only, not sent)"))
    return _wa_send_flow(contact_or_phone, message, send)

# ---------------------------------------------------------------- plan execution
def _wait(seconds):
    end = time.time() + min(120, max(0.2, float(seconds)))
    while time.time() < end:
        if _stopped(): return
        time.sleep(0.3)

def _run_step(step, auto_send):
    """Execute one plan step. Returns a short result line."""
    from . import pc
    a = step.get("action")
    if a == "open_app": return pc.open_app(step.get("name", ""))
    if a == "open_url": return pc.open_website(step.get("url", ""))
    if a == "play_youtube": return pc.play_on_youtube(step.get("query", ""))
    if a == "search_google": return pc.google_search(step.get("query", ""))
    if a == "whatsapp":
        return whatsapp_message(step.get("contact", ""), step.get("message", ""),
                                send=bool(step.get("send", True)), auto_send=auto_send)
    if a == "type": return pc.type_text(step.get("text", ""))
    if a == "key": return pc.press_keys(step.get("keys", "enter"))
    if a == "click": return pc.find_and_click(step.get("what", ""))
    if a == "wait":
        _wait(step.get("seconds", 3)); return "Waited."
    return "Unknown step skipped: " + str(a)

def _describe(step):
    a = step.get("action")
    if a == "open_app": return step.get("name", "") + " khol raha hoon"
    if a == "open_url": return step.get("url", "") + " khol raha hoon"
    if a == "play_youtube": return "YouTube pe '" + step.get("query", "") + "' chala raha hoon"
    if a == "search_google": return "Google pe '" + step.get("query", "") + "' search kar raha hoon"
    if a == "whatsapp":
        return "WhatsApp pe " + step.get("contact", "") + " ko message " + ("bhej raha hoon" if step.get("send", True) else "type kar raha hoon")
    if a == "type": return "Type kar raha hoon"
    if a == "key": return step.get("keys", "") + " daba raha hoon"
    if a == "click": return "'" + step.get("what", "") + "' click kar raha hoon"
    if a == "wait": return str(step.get("seconds", 3)) + " second ruk raha hoon"
    return str(a)

def execute(steps, auto_send=False, dry_run=None):
    """Run a plan step by step with HUD feedback. Honors bus.stop between steps."""
    from . import pc
    dry = DRY_RUN if dry_run is None else dry_run
    if not steps:
        return "Is request ke liye steps nahi ban paaye. Thoda alag tareeke se bolo."
    if getattr(bus, "locked", False):
        return "PC control LOCKED hai. HUD me switch ARMED karo pehle."
    clear_stop()
    done = []
    total = len(steps)
    for i, step in enumerate(steps, 1):
        if _stopped():
            bus.log("info", "Plan rok diya gaya (user ne kaha).")
            return f"Rok diya. {i - 1}/{total} steps ho chuke the."
        _log(f"Step {i}/{total}: {_describe(step)}")
        try:
            if dry:
                a = dict(step); a.pop("action", None)
                res = "[DRY RUN] " + step.get("action", "?") + " " + json.dumps(a, ensure_ascii=False)
                if step.get("action") == "whatsapp" and step.get("send", True) and not auto_send:
                    res = whatsapp_message(step.get("contact", ""), step.get("message", ""), True, auto_send)
            else:
                res = _run_step(step, auto_send)
        except Exception as e:
            res = f"ERROR: {e}"
        done.append(res)
        _log("  -> " + str(res)[:90])
        if "User said no" in str(res):
            return f"Theek hai, wahin rok diya. {i - 1}/{total} steps poori hui."
        if not dry and i < total:
            _wait(1.0)
    if _stopped():
        return f"Rok diya gaya. {len(done)}/{total} steps poori hui."
    return f"Ho gaya - {total} steps poori: " + "; ".join(str(r)[:60] for r in done[-3:])

# ---------------------------------------------------------------- plan generation
def _valid(step):
    return isinstance(step, dict) and step.get("action") in ACTIONS

def _extract_json(text):
    if not text: return None
    m = re.search(r"\[.*\]", text, re.S)
    if not m: return None
    try:
        steps = json.loads(m.group(0))
    except Exception:
        return None
    return [s for s in steps if _valid(s)] or None

# ---------------- offline Hinglish parser (no brain needed) ----------------
_SPLIT = re.compile(r"\b(?:phir|fir|uske baad|iske baad|phir se|and then|then|aur phir|aur fir)\b|,\s*(?:aur|phir|fir)\s*|\s+aur\s+|,\s*(?=[^,]*?(?:kholo|kholke|kholkar|open|chalao|bajao|play|search|whatsapp|google|enter\s*daba|wait|ruko))", re.I)

_OPEN_APP = re.compile(r"(?:^|\b)(?P<name>chrome|google chrome|whatsapp desktop|notepad|calculator|calc|paint|spotify|vlc|vscode|vs code|file explorer|explorer|cmd|powershell|settings|word|excel|powerpoint|edge|firefox)\s+(?:kholo|khul|open\s*karo|open\s*kar|open|chalao|chalu\s*karo|start\s*karo)", re.I)
_YT = re.compile(r"(?:youtube\s*(?:pe|par|per|me)?\s*)?(?P<q>.+?)\s*(?:gaana|gana|song|video)?\s*(?:chalao|chala\s*do|bajao|baja\s*do|play\s*karo|play\s*kar|play|lagao|laga\s*do|suna\s*do|sunao)$", re.I)
_GOOGLE = re.compile(r"google\s*(?:pe|par|per)?\s*(?P<q>.+?)\s*search\s*(?:karo|kar\s*do|kar)?$", re.I)
_WA = re.compile(r"whatsapp\s*(?:pe|par|per|me)?\s*(?P<who>.+?)\s*ko\s*(?:(?:message|msg|messege)\s*(?:karo|kar|bhejo|bhej\s*do|likho|likh\s*do|bhej|kar\s*do)\s*[:\-]?\s*)?(?P<msg>.+)$", re.I)
_KEY = re.compile(r"(?P<keys>enter|tab|escape|esc|space|backspace|delete|ctrl\s*\+\s*\w+|alt\s*\+\s*\w+|win\s*\+\s*\w+)\s*(?:daba\s*do|dabao|daba|press\s*karo|press\s*kar|press|karo)$", re.I)
_URL = re.compile(r"(?P<url>(?:https?://)?[\w\-]+(?:\.[\w\-]+)+(?:/\S*)?)\s*(?:kholo|khol\s*do|open\s*karo|open)$", re.I)
_WAIT = re.compile(r"(?P<n>\d+)\s*(?:second|sec|minute|min)\s*(?:ruko|ruk|wait\s*karo|wait)", re.I)

_YT_HINT = re.compile(r"youtube|gaana|gana|song|video|chalao|bajao|play|lagao|sunao", re.I)
_WA_HINT = re.compile(r"whatsapp", re.I)

def _clean_msg(msg):
    msg = re.sub(r"\s*(?:likh\s*do|likho|likh|karo|kar\s*do|kar|bhej\s*do|bhejo|bhej|send\s*karo|send\s*kar\s*do|send)$", "", msg.strip())
    return msg.strip(" .,:-")

def _parse_clause(clause):
    c = clause.strip(" ,.!")
    if not c: return None
    low = c.lower()
    # 'whatsapp open karke / kholke / kholo X ko message karo' -> plain whatsapp command
    low = re.sub(r"whatsapp\s+(?:open\s*karke|kholke|kholkar|khol\s*kar|kholo|khol|open\s*karo|open)\b", "whatsapp", low)
    m = _WA.search(low)
    if m and _WA_HINT.search(low):
        who = m.group("who").strip(" .")
        msg = m.group("msg").strip(" .:,-")
        send = True
        km = _KEY.search(msg)
        if km and "enter" in km.group("keys"):
            msg = _KEY.sub("", msg).strip(" .,")
            send = True
        if re.search(r"\b(?:mat bhejo|bhejna mat|type hi karo|sirf likho)\b", msg):
            msg = re.sub(r"\b(?:mat bhejo|bhejna mat|type hi karo|sirf likho)\b", "", msg).strip(" .,")
            send = False
        msg = _clean_msg(msg)
        if who and msg:
            return {"action": "whatsapp", "contact": who, "message": msg, "send": send}
    m = _GOOGLE.search(low)
    if m: return {"action": "search_google", "query": m.group("q").strip()}
    m = _OPEN_APP.search(low)
    if m: return {"action": "open_app", "name": m.group("name").lower()}
    m = _URL.search(low)
    if m: return {"action": "open_url", "url": m.group("url")}
    m = _WAIT.search(low)
    if m:
        n = int(m.group("n")) * (60 if "min" in m.group(0) else 1)
        return {"action": "wait", "seconds": n}
    km = _KEY.search(low)
    if km and re.search(r"daba|press", low):
        return {"action": "key", "keys": km.group("keys").replace(" ", "")}
    if _YT_HINT.search(low):
        q = low
        q = re.sub(r"\byoutube\s*(?:pe|par|per|me)?\b", "", q)
        q = re.sub(r"^chrome\s*(?:pe|par|per|me|kholke|khol\s*kar|kholkar)?\s*", "", q)
        m = _YT.search(q.strip())
        if m:
            query = m.group("q").strip()
            query = re.sub(r"^(?:mujhe\s+)?", "", query)
            if query:
                return {"action": "play_youtube", "query": query}
    return None

def parse_steps_local(goal):
    """Offline Hinglish command splitter: 'chrome kholo, youtube pe X chalao' -> steps.
    Handles chrome/open-site prefixes like 'chrome kholke youtube pe ...' in one clause."""
    goal = (goal or "").strip()
    if not goal: return []
    steps = []
    # 'chrome kholke/kholkar ...' at the start = open chrome first, then the rest
    m = re.search(r"chrome\s*(?:kholke|khol\s*kar|kholkar|open\s*karke)\s+(.+)$", goal, re.I)
    if m:
        steps.append({"action": "open_app", "name": "chrome"})
        goal = m.group(1).strip()
    for clause in _SPLIT.split(goal):
        st = _parse_clause(clause)
        if st:
            if steps and steps[-1] == st: continue
            # '...ko message karo' + 'enter daba do' = send the typed message
            if st["action"] == "key" and st["keys"].startswith("enter") and steps and steps[-1]["action"] == "whatsapp":
                steps[-1]["send"] = True
                continue
            steps.append(st)
    return steps

def plan_steps(goal):
    """Brain-written JSON plan first; offline parser as fallback."""
    try:
        text = gen(PLAN_PROMPT.format(goal=goal))
    except Exception:
        text = None
    steps = _extract_json(text)
    if steps:
        _log("Plan taiyaar (brain): " + " -> ".join(s["action"] for s in steps))
        return steps
    steps = parse_steps_local(goal)
    if steps:
        _log("Plan taiyaar (offline parser): " + " -> ".join(s["action"] for s in steps))
    return steps

# ---------------------------------------------------------------- tools for the brain
def plan_and_do(goal: str, auto_send: bool = False) -> str:
    """Do a multi-step job on the PC like a human, from ONE Hinglish sentence: open apps/sites, play a YouTube song, Google search, WhatsApp someone a message (finds the chat by name, types, presses Enter), type text, press keys, click visible buttons, wait. Shows every step in the HUD and can be stopped with 'ruk jao Jarvis'. auto_send=True ONLY when the user's own command said 'bina puche bhej do' - otherwise WhatsApp sending asks first."""
    if re.search(r"bina puche|bina puchhe|bina pooche", goal or "", re.I):
        auto_send = True
        goal = re.sub(r"bina puche|bina puchhe|bina pooche", "", goal, flags=re.I).strip(" ,.-")
    steps = plan_steps(goal)
    return execute(steps, auto_send=auto_send)

def stop_everything() -> str:
    """Immediately stop the currently running multi-step plan or GUI automation ('ruk jao Jarvis', 'stop karo')."""
    request_stop()
    return "Rok diya. Jo step chal raha tha, wahi ruka."

AGENT_TOOLS = [plan_and_do, whatsapp_message, stop_everything]
