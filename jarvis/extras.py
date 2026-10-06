"""Feature Pack 2 + Self-improvement. Every function is a tool for the brain.
Self-modification rules: ONLY with the user's spoken/typed yes, always logged in data/changes.log,
always with a backup copy in data/backups/, and a failed change is rolled back automatically.
Nothing here changes code on its own."""
import os, re, sys, json, time, shutil, threading, datetime, hashlib, subprocess, urllib.request, py_compile, zipfile, io
from pathlib import Path
from . import config, bus

DATA = config.DATA_DIR
BACKUPS = DATA / "backups"; PLUGINS = DATA / "plugins"
CHANGES = DATA / "changes.log"; ERRORS = DATA / "errors.log"
SKILLS = DATA / "skills.json"; TURNS = DATA / "turns.json"; USAGE = DATA / "usage.json"
PLUGINS.mkdir(exist_ok=True); BACKUPS.mkdir(exist_ok=True)

def _pc():
    from . import pc
    return pc

def _say(text):
    try: _pc().notify(text)
    except Exception: print(text)

def _client():
    from google import genai
    return genai.Client(api_key=config.GEMINI_API_KEY)

def _gen(prompt, model=None):
    last = None
    for m in ([model] if model else config.MODEL_CHAIN[:5]):
        try:
            r = _client().models.generate_content(model=m, contents=prompt)
            t = (r.text or "").strip()
            if t: return t
        except Exception as ex: last = ex
    raise last or RuntimeError("no answer")

def _jload(p, d):
    try: return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception: return d
def _jsave(p, v):
    Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")

def _log_change(text):
    with open(CHANGES, "a", encoding="utf-8") as f: f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")

# =============================================================== 1. morning briefing
def morning_briefing() -> str:
    """Collect weather, news, notes, today's alarms and PC battery for a spoken morning briefing. Summarise it warmly in Hinglish."""
    pc = _pc(); parts = []
    parts.append("TIME: " + datetime.datetime.now().strftime("%A %d %B, %I:%M %p"))
    parts.append("WEATHER: " + pc.get_weather(config.WEATHER_CITY))
    parts.append("NEWS:\n" + pc.get_news("India", 5))
    parts.append("NOTES:\n" + pc.read_notes(8))
    try:
        import psutil
        b = psutil.sensors_battery()
        if b: parts.append(f"BATTERY: {int(b.percent)}%")
        parts.append(f"DISK FREE: {int(shutil.disk_usage(str(Path.home().anchor or '/')).free / 2**30)} GB")
    except Exception: pass
    return "\n\n".join(parts)

# =============================================================== 2. dictation mode
_dict = {"on": False}
def dictation_mode(action: str = "start") -> str:
    """Start or stop dictation. While on, everything the user says is typed into the active app. action: start | stop."""
    if action == "stop":
        _dict["on"] = False; return "Dictation band."
    if _dict["on"]: return "Dictation already on hai."
    _dict["on"] = True
    def loop():
        from . import listen
        import pyperclip, pyautogui
        c = _client()
        while _dict["on"]:
            try:
                wav = listen.record(max_wait=6.0)
                if not wav: continue
                t = (listen.transcribe(wav, c) or "").strip()
                if not t: continue
                low = t.lower()
                if re.search(r"(dictation (band|stop)|stop dictation|dictation khatam)", low):
                    _dict["on"] = False; _say("Dictation band."); break
                old = pyperclip.paste()
                pyperclip.copy(t + " "); pyautogui.hotkey("ctrl", "v"); time.sleep(0.2); pyperclip.copy(old)
            except Exception as e:
                bus.log("info", f"dictation: {str(e)[:80]}"); time.sleep(1)
    threading.Thread(target=loop, daemon=True).start()
    return "Dictation shuru. Jis app me type karna hai usme click karke bolo. Rokne ke liye bolo 'dictation band'."

# =============================================================== 3. content search
def search_file_contents(query: str, folder: str = "Documents", max_results: int = 8) -> str:
    """Find files by what is INSIDE them (txt, md, py, csv, json, docx, pdf if pypdf is installed). Example: 'Linux commands'."""
    pc = _pc(); root = Path(pc._p(folder)); words = [w for w in re.split(r"\W+", query.lower()) if len(w) > 2]
    if not words: return "Search ke liye koi word batao."
    out = []; t0 = time.time(); scanned = 0
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if not d.startswith(".") and d not in ("node_modules", "__pycache__", "venv", ".git")]
        for f in fn:
            ext = f.rsplit(".", 1)[-1].lower() if "." in f else ""
            if ext not in ("txt", "md", "py", "csv", "json", "log", "docx", "pdf", "html", "c", "cpp", "java", "js"): continue
            p = os.path.join(dp, f)
            try:
                if os.path.getsize(p) > 15_000_000: continue
                text = ""
                if ext == "docx":
                    with zipfile.ZipFile(p) as z: text = re.sub(r"<[^>]+>", " ", z.read("word/document.xml").decode("utf8", "ignore"))
                elif ext == "pdf":
                    from pypdf import PdfReader
                    text = " ".join((pg.extract_text() or "") for pg in PdfReader(p).pages[:40])
                else:
                    text = open(p, "r", encoding="utf-8", errors="ignore").read(400_000)
                scanned += 1
                low = (text + " " + f).lower(); score = sum(low.count(w) for w in words)
                if all(w in low for w in words) or (len(words) > 2 and sum(w in low for w in words) >= len(words) - 1):
                    out.append((score, p))
            except Exception: pass
            if time.time() - t0 > 40: break
    out.sort(reverse=True)
    if not out: return f"{scanned} files dekhi, '{query}' kisi me nahi mila. (PDF ke liye: pip install pypdf)"
    return f"{len(out)} match ({scanned} files scanned):\n" + "\n".join(p for _, p in out[:max_results])

# =============================================================== 4. watch mode
_watches = {}
def watch_website(url: str, keyword: str = "", every_minutes: int = 30) -> str:
    """Watch a web page and speak up when it changes (or when a keyword appears). Stop with stop_watching."""
    import requests
    def snap():
        t = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"}).text
        t = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", t, flags=re.S)
        return re.sub(r"\s+", " ", t).strip()
    try: base = snap()
    except Exception as e: return f"Page khul nahi raha: {e}"
    ev = threading.Event(); _watches[url] = ev
    def loop():
        last = hashlib.md5(base.encode()).hexdigest(); had = keyword.lower() in base.lower() if keyword else False
        while not ev.wait(max(5, every_minutes) * 60):
            try: t = snap()
            except Exception: continue
            h = hashlib.md5(t.encode()).hexdigest()
            if keyword:
                if keyword.lower() in t.lower() and not had: _say(f"Khabar: {url} par '{keyword}' aa gaya hai."); had = True
                elif keyword.lower() not in t.lower(): had = False
            elif h != last: _say(f"Khabar: {url} update ho gaya hai.")
            last = h
    threading.Thread(target=loop, daemon=True).start()
    return f"Watch shuru: {url} har {every_minutes} min check hoga" + (f" ('{keyword}' ke liye)." if keyword else ".")
def stop_watching(url: str = "") -> str:
    """Stop watching one website (or all if url is empty)."""
    ks = [url] if url in _watches else (list(_watches) if not url else [])
    for k in ks: _watches.pop(k).set()
    return f"{len(ks)} watch band." if ks else "Aisi koi watch nahi chal rahi."

# =============================================================== 5. meeting mode
_meet = {"on": False, "text": [], "t0": 0}
def meeting_mode(action: str = "start") -> str:
    """Listen to a meeting/video/call through the microphone and write notes. action: start | stop. Stop returns notes + summary and saves them in Documents/Jarvis-Meetings."""
    if action == "start":
        if _meet["on"]: return "Meeting mode already on hai."
        _meet.update(on=True, text=[], t0=time.time())
        def loop():
            from . import listen
            c = _client()
            while _meet["on"]:
                try:
                    wav = listen.record(max_wait=15.0, max_len=45.0, silence_end=1.8)
                    if wav:
                        t = (listen.transcribe(wav, c) or "").strip()
                        if t: _meet["text"].append(t)
                except Exception: time.sleep(1)
        threading.Thread(target=loop, daemon=True).start()
        return "Meeting mode on. Speaker ki awaaz mic tak pahunchni chahiye (speaker on rakho). Khatam hone par bolo 'meeting khatam'."
    _meet["on"] = False; time.sleep(1.5)
    raw = "\n".join(_meet["text"])
    if not raw: return "Kuch sunai nahi diya, notes khaali hain."
    try: notes = _gen("Meeting transcript (Hindi/English mix). Write short clear notes in simple Hinglish: summary, key points, decisions, action items.\n\n" + raw)
    except Exception: notes = raw
    d = Path.home() / "Documents" / "Jarvis-Meetings"; d.mkdir(parents=True, exist_ok=True)
    f = d / time.strftime("meeting-%Y%m%d-%H%M.txt"); f.write_text(notes + "\n\n--- TRANSCRIPT ---\n" + raw, encoding="utf-8")
    return f"Notes saved: {f}\n\n{notes[:1500]}"

# =============================================================== 6. usage report
_usage_on = [False]
def _usage_loop():
    try: import pygetwindow as gw
    except Exception: return
    while True:
        time.sleep(15)
        try:
            w = gw.getActiveWindow(); title = (w.title if w else "") or "Idle"
            app = title.split(" - ")[-1].strip()[:40] or "Idle"
            u = _jload(USAGE, {}); day = time.strftime("%Y-%m-%d")
            u.setdefault(day, {}); u[day][app] = u[day].get(app, 0) + 15
            _jsave(USAGE, u)
        except Exception: pass
def start_usage_tracking():
    if not _usage_on[0] and sys.platform.startswith("win"):
        _usage_on[0] = True; threading.Thread(target=_usage_loop, daemon=True).start()
def usage_report(days: int = 1) -> str:
    """Report how much time went in which app today (days=1) or the last N days."""
    u = _jload(USAGE, {}); tot = {}
    for i in range(max(1, days)):
        d = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        for a, s in u.get(d, {}).items(): tot[a] = tot.get(a, 0) + s
    if not tot: return "Abhi tak koi usage data nahi (tracking Jarvis chalne par shuru hoti hai)."
    rows = sorted(tot.items(), key=lambda x: -x[1])[:8]
    return "App usage:\n" + "\n".join(f"{a}: {int(s // 3600)}h {int(s % 3600 // 60)}m" for a, s in rows)

# =============================================================== 7. PC watchdog
_dog = [False]
def _dog_loop():
    import psutil
    cool = {}
    def warn(k, msg):
        if time.time() - cool.get(k, 0) > 3600: cool[k] = time.time(); _say(msg)
    while True:
        time.sleep(60)
        try:
            du = psutil.disk_usage(str(Path.home().anchor or "/"))
            if du.percent > 90: warn("disk", f"Dhyan do, disk {int(du.percent)} percent bhari hai. Safai karoon?")
            if psutil.virtual_memory().percent > 92: warn("ram", "RAM almost full hai, PC slow ho sakta hai.")
            b = psutil.sensors_battery()
            if b and not b.power_plugged and b.percent < 20: warn("bat", f"Battery sirf {int(b.percent)} percent hai, charger lagao.")
            if hasattr(psutil, "sensors_temperatures"):
                for n, es in (psutil.sensors_temperatures() or {}).items():
                    for e in es:
                        if e.current and e.current > 90: warn("heat", f"PC bahut garam hai, {int(e.current)} degree.")
        except Exception: pass
def start_watchdog():
    if not _dog[0]:
        try: import psutil
        except Exception: return
        _dog[0] = True; threading.Thread(target=_dog_loop, daemon=True).start()
def watchdog_status() -> str:
    """Show PC health now: disk, RAM, battery, heat. (The watchdog also alerts on its own.)"""
    import psutil
    du = psutil.disk_usage(str(Path.home().anchor or "/")); b = psutil.sensors_battery()
    return f"Disk {int(du.percent)}% used, RAM {int(psutil.virtual_memory().percent)}%, CPU {int(psutil.cpu_percent(1))}%" + (f", battery {int(b.percent)}%" if b else "") + ". Watchdog " + ("ON" if _dog[0] else "OFF")

# =============================================================== 8. voice music
def play_music(song: str) -> str:
    """Play a song on YouTube hands-free. Example: 'Arijit Singh Tum Hi Ho'."""
    return _pc().play_on_youtube(song + " official audio")
def music_control(action: str) -> str:
    """action: pause | play | next | previous | stop | volume_up | volume_down | mute (media keys)."""
    import pyautogui
    keys = {"pause": "playpause", "play": "playpause", "stop": "stop", "next": "nexttrack", "previous": "prevtrack",
            "volume_up": "volumeup", "volume_down": "volumedown", "mute": "volumemute"}
    k = keys.get(action.lower().replace(" ", "_"))
    if not k: return "Unknown action."
    pyautogui.press(k); return "Done."

# =============================================================== SELF-IMPROVEMENT
def _backup(files, label):
    d = BACKUPS / (time.strftime("%Y%m%d-%H%M%S") + "-" + re.sub(r"\W+", "_", label)[:30]); d.mkdir(parents=True, exist_ok=True)
    meta = []
    for f in files:
        f = Path(f)
        if f.exists():
            rel = f.relative_to(config.ROOT); (d / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, d / rel); meta.append(str(rel))
        else: meta.append("NEW:" + str(f.relative_to(config.ROOT)))
    _jsave(d / "meta.json", meta); return d

def _restore(d):
    d = Path(d)
    for rel in _jload(d / "meta.json", []):
        if rel.startswith("NEW:"):
            try: (config.ROOT / rel[4:]).unlink()
            except Exception: pass
        else:
            shutil.copy2(d / rel, config.ROOT / rel)

def _ask(q):
    return _pc().confirm(q)

SAFE_NAME = re.compile(r"^[a-z][a-z0-9_]{2,40}$")

# ---- plugin loading (self-made tools live in data/plugins/*.py)
def load_plugins():
    import importlib.util
    pc = _pc(); n = 0
    for f in sorted(PLUGINS.glob("*.py")):
        try:
            spec = importlib.util.spec_from_file_location("jarvis_plugin_" + f.stem, f)
            m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
            for fn in getattr(m, "TOOLS", []):
                if fn.__name__ not in pc._seen:
                    pc._seen.add(fn.__name__); pc.TOOLS.append(pc._wrap(fn)); n += 1
        except Exception as e:
            _log_err(f"plugin {f.name}: {e}")
    return n

def _log_err(text):
    try:
        with open(ERRORS, "a", encoding="utf-8") as f: f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text[:600]}\n")
    except Exception: pass

# ---- 1) self-coding
def create_new_tool(what_it_should_do: str, tool_name: str) -> str:
    """Self-coding: write a NEW tool (python function) for Jarvis. Asks the user's permission first, keeps a backup, loads it live. tool_name: lowercase_with_underscores."""
    if not SAFE_NAME.match(tool_name): return "tool_name lowercase letters/underscores me do (jaise: pdf_merge)."
    if tool_name in _pc()._seen: return "Is naam ka tool pehle se hai."
    prompt = ("Write ONE Python module for a Windows desktop assistant. It must define exactly one public function "
              f"`{tool_name}` with type-hinted simple args (str/int/float/bool) and a short docstring, returning a short str, "
              f"plus the line `TOOLS = [{tool_name}]`. Use only the standard library plus: requests, pyautogui, psutil, pyperclip, pathlib. "
              "No network downloads of code, no os.system/subprocess unless the task truly needs it, never delete files. "
              f"Task: {what_it_should_do}\nReturn ONLY the code, no markdown fences.")
    code = re.sub(r"^```\w*\n|```$", "", _gen(prompt).strip(), flags=re.M).strip()
    f = PLUGINS / f"{tool_name}.py"
    try: compile(code, str(f), "exec")
    except SyntaxError as e: return f"Code galat bana ({e}). Kuch nahi badla."
    risky = re.findall(r"\b(subprocess|os\.system|shutil\.rmtree|os\.remove|eval\(|exec\(|__import__)", code)
    short = f"'{tool_name}' naam ka naya tool: {what_it_should_do[:120]}. " + (f"Dhyan: code me {', '.join(set(risky))} hai. " if risky else "") + "Add kar doon?"
    if not _ask("Main apne aap me naya feature jodna chahta hoon. " + short): return "Theek hai, kuch nahi badla."
    b = _backup([f], "newtool_" + tool_name)
    f.write_text(code, encoding="utf-8"); _log_change(f"NEW TOOL {tool_name}: {what_it_should_do[:150]} (backup {b.name})")
    n = load_plugins(); _pc().brain_reload()
    return f"Naya tool '{tool_name}' add ho gaya ({n} loaded). Code: {f}. Hataana ho to bolo 'last change undo karo'." if n else (_restore(b) or "Tool load nahi hua, wapas hata diya.")

# ---- 2) self-healing
def self_heal(extra_hint: str = "") -> str:
    """Self-healing: look at recent errors in data/errors.log, propose a fix to ONE file, ask the user, backup, apply, compile-check, roll back on failure. Takes effect after restart."""
    errs = ERRORS.read_text(encoding="utf-8", errors="ignore")[-3000:] if ERRORS.exists() else ""
    if not errs and not extra_hint: return "Koi recent error log me nahi hai. Sab theek lag raha hai."
    m = re.findall(r'([\w/\\]+\.py)', errs + extra_hint)
    cand = [config.ROOT / "jarvis" / Path(x).name for x in m if (config.ROOT / "jarvis" / Path(x).name).exists()] + list(PLUGINS.glob("*.py"))
    target = None
    for c in cand:
        if c.name in (errs + extra_hint): target = c; break
    if not target: return "Error kis file ka hai ye pakad nahi paya. Errors:\n" + errs[-600:]
    src = target.read_text(encoding="utf-8")
    new = re.sub(r"^```\w*\n|```$", "", _gen(f"This Python file has a bug. Recent errors:\n{errs}\n{extra_hint}\n\nFile {target.name}:\n{src}\n\nReturn the COMPLETE fixed file only, minimal changes, no markdown fences.").strip(), flags=re.M).strip()
    try: compile(new, target.name, "exec")
    except SyntaxError as e: return f"Fix galat bana ({e}), kuch nahi badla."
    import difflib
    diff = [l for l in difflib.unified_diff(src.splitlines(), new.splitlines(), lineterm="", n=0) if l[:1] in "+-" and l[:3] not in ("+++", "---")]
    if not diff: return "Koi change ki zarurat nahi mili."
    if not _ask(f"{target.name} me bug mila. Fix me {len(diff)} lines badlengi. Backup le kar fix kar doon?"): return "Theek hai, kuch nahi badla."
    b = _backup([target], "heal_" + target.stem); target.write_text(new + "\n", encoding="utf-8")
    try: py_compile.compile(str(target), doraise=True)
    except Exception as e: _restore(b); return f"Fix fail hua, purana wapas laga diya ({e})."
    _log_change(f"HEAL {target.name}: {len(diff)} lines (backup {b.name})"); ERRORS.write_text("", encoding="utf-8")
    return f"{target.name} fix ho gaya. Jarvis restart karo taaki laage. Diff preview:\n" + "\n".join(diff[:12])

def undo_last_change() -> str:
    """Roll back the most recent self-change (self-coded tool, bug fix or update) from its backup copy."""
    bs = sorted([p for p in BACKUPS.iterdir() if (p / "meta.json").exists()])
    if not bs: return "Koi backup nahi hai."
    b = bs[-1]
    if not _ask(f"Last change '{b.name}' wapas karoon?"): return "Theek hai."
    _restore(b); shutil.move(str(b), str(BACKUPS / ("undone-" + b.name))); _log_change(f"UNDO {b.name}"); load_plugins(); _pc().brain_reload()
    return "Last change undo ho gaya. Restart karo agar core file thi."

def show_change_log(last: int = 10) -> str:
    """Show what Jarvis changed in itself (changes log)."""
    return "\n".join(CHANGES.read_text(encoding="utf-8").splitlines()[-last:]) if CHANGES.exists() else "Abhi tak koi self-change nahi hua."

# ---- 3) auto-update
def _repo():
    return os.getenv("JARVIS_REPO", "AKASH991833/jarvis-mark-1").strip(), os.getenv("GITHUB_TOKEN", "").strip()
def _gh(url, binary=False):
    repo, tok = _repo(); h = {"User-Agent": "jarvis"}
    if tok: h["Authorization"] = "Bearer " + tok
    r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40).read()
    return r if binary else r.decode("utf-8", "ignore")
def _local_version(): 
    try: return (config.ROOT / "VERSION").read_text().strip()
    except Exception: return "0"
def check_for_update() -> str:
    """Check the GitHub repo for a newer Jarvis version (never installs by itself)."""
    repo, tok = _repo()
    try: v = _gh(f"https://raw.githubusercontent.com/{repo}/main/VERSION").strip()
    except Exception as e:
        return ("Update check nahi ho paya. Repo private ho sakta hai: .env me GITHUB_TOKEN daalo ya repo public karo. (" + str(e)[:60] + ")")
    return f"Latest {v}, tumhare paas {_local_version()}. " + ("Update available hai!" if v != _local_version() else "Tum latest ho.")
def apply_update() -> str:
    """Download the newest Jarvis from GitHub and install it (asks first, backs up, keeps .env and data)."""
    repo, tok = _repo()
    try: z = zipfile.ZipFile(io.BytesIO(_gh(f"https://api.github.com/repos/{repo}/zipball/main", True)))
    except Exception as e: return "Update download nahi hua: " + str(e)[:80]
    names = [n for n in z.namelist() if n.endswith((".py", ".bat", ".txt", "VERSION", ".md", ".example")) and not n.endswith("/")]
    prefix = z.namelist()[0].split("/")[0] + "/"
    items = {n[len(prefix):]: n for n in names if not n[len(prefix):].startswith(("data/", ".env"))}
    items = {k: v for k, v in items.items() if k and not re.match(r"^\d+-", Path(k).name)}
    if not items: return "Repo me valid files nahi mili."
    if not _ask(f"{len(items)} files ka naya Jarvis update install karoon? Backup le loonga."): return "Theek hai, update nahi kiya."
    b = _backup([config.ROOT / k for k in items], "update")
    try:
        for k, n in items.items():
            p = config.ROOT / k; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(z.read(n))
            if k.endswith(".py"): py_compile.compile(str(p), doraise=True)
    except Exception as e: _restore(b); return f"Update fail hua, purana wapas laga diya ({str(e)[:60]})."
    _log_change(f"UPDATE to {_local_version()} ({len(items)} files, backup {b.name})")
    return "Update ho gaya. Jarvis restart karo (run.bat). Gadbad ho to bolo 'last change undo karo'."

# ---- 4) skill learning
def begin_turn(text):
    """Called by the brain at every user request."""
    global _cur
    _cur = {"q": text, "calls": [], "t": time.time()}
    t = _jload(TURNS, []); t.append(_cur); _jsave(TURNS, t[-300:])
_cur = None
def record_call(name, kwargs):
    global _cur
    if _cur is not None and name not in ("learn_skills", "save_skill", "run_skill", "list_skills"):
        _cur["calls"].append({"tool": name, "args": kwargs})
        t = _jload(TURNS, [])
        if t: t[-1] = _cur; _jsave(TURNS, t)
def learn_skills() -> str:
    """Skill learning: look at past requests and suggest shortcuts for tasks the user repeats (same tool steps 3+ times)."""
    t = [x for x in _jload(TURNS, []) if x.get("calls")]; seq = {}
    for x in t:
        k = json.dumps([[c["tool"], c["args"]] for c in x["calls"]], sort_keys=True)
        seq.setdefault(k, []).append(x["q"])
    best = [(len(v), v[-1], json.loads(k)) for k, v in seq.items() if len(v) >= 3]
    if not best: return "Abhi koi baar-baar wala kaam nahi mila (kam se kam 3 baar same kaam chahiye)."
    best.sort(reverse=True)
    return "Ye kaam tum baar-baar karte ho:\n" + "\n".join(f"- ({n}x) '{q}' -> steps: {[s[0] for s in st]}" for n, q, st in best[:5]) + "\nShortcut banau? (save_skill se naam do)"
def save_skill(name: str, what_it_replays_request: str) -> str:
    """Save a learned shortcut. what_it_replays_request = the user's earlier request text to replay as steps. Asks permission."""
    t = [x for x in _jload(TURNS, []) if x.get("calls") and x["q"].strip().lower() == what_it_replays_request.strip().lower()]
    if not t: return "Wo request history me nahi mili."
    steps = t[-1]["calls"]
    if not _ask(f"Shortcut '{name}' save karoon? Ye {len(steps)} steps chalayega: {', '.join(s['tool'] for s in steps)}."): return "Theek hai."
    s = _jload(SKILLS, {}); s[name.lower()] = steps; _jsave(SKILLS, s); _log_change(f"SKILL {name}: {len(steps)} steps")
    return f"Shortcut '{name}' ban gaya. Bolo 'run skill {name}'."
def list_skills() -> str:
    """List saved shortcut skills."""
    s = _jload(SKILLS, {}); return "\n".join(f"{k}: {[x['tool'] for x in v]}" for k, v in s.items()) or "Abhi koi skill saved nahi."
def run_skill(name: str) -> str:
    """Run a saved shortcut skill. Dangerous steps still ask for confirmation by themselves."""
    steps = _jload(SKILLS, {}).get(name.lower())
    if not steps: return "Aisi skill nahi hai. " + list_skills()
    pc = _pc(); byname = {t.__name__: t for t in pc.TOOLS}; res = []
    for s in steps:
        fn = byname.get(s["tool"])
        res.append(f"{s['tool']}: {str(fn(**s['args']))[:100]}" if fn else f"{s['tool']}: missing")
    return "\n".join(res)

EXTRA_TOOLS = [morning_briefing, dictation_mode, search_file_contents, watch_website, stop_watching, meeting_mode, usage_report,
               watchdog_status, play_music, music_control, create_new_tool, self_heal, undo_last_change, show_change_log,
               check_for_update, apply_update, learn_skills, save_skill, list_skills, run_skill]
def start_background():
    start_usage_tracking(); start_watchdog()

# =============================================================== Google Calendar (no OAuth needed)
def add_calendar_event(title: str, start_iso: str, duration_minutes: int = 60, details: str = "") -> str:
    """Add an event/reminder to Google Calendar. start_iso like 2026-10-07T18:30 (local time). Opens a pre-filled Google Calendar page; the user only clicks Save."""
    import urllib.parse, webbrowser
    try: s = datetime.datetime.fromisoformat(start_iso)
    except Exception: return "Time ka format samajh nahi aaya. Example: 2026-10-07T18:30"
    e = s + datetime.timedelta(minutes=duration_minutes); f = "%Y%m%dT%H%M%S"
    url = "https://calendar.google.com/calendar/render?action=TEMPLATE&" + urllib.parse.urlencode(
        {"text": title, "dates": f"{s.strftime(f)}/{e.strftime(f)}", "details": details})
    webbrowser.open(url)
    return f"Google Calendar khul gaya, '{title}' {s.strftime('%d %b %I:%M %p')} ke liye bhara hua hai. Bas Save dabao."
def calendar_events(days: int = 2) -> str:
    """Read upcoming Google Calendar events. Needs GCAL_ICAL_URL in .env (Calendar settings > Secret address in iCal format)."""
    import requests
    url = os.getenv("GCAL_ICAL_URL", "").strip()
    if not url: return "Calendar padhne ke liye .env me GCAL_ICAL_URL daalo (Google Calendar > Settings > Integrate calendar > Secret address in iCal format). Naya event add karna iske bina bhi chalta hai."
    txt = requests.get(url, timeout=25).text.replace("\r\n ", ""); now = datetime.datetime.now(); out = []
    for blk in txt.split("BEGIN:VEVENT")[1:]:
        m = re.search(r"DTSTART[^:]*:(\d{8})(T(\d{6}))?", blk); sm = re.search(r"SUMMARY[^:]*:(.*)", blk)
        if not (m and sm): continue
        d = datetime.datetime.strptime(m.group(1) + (m.group(3) or "000000"), "%Y%m%d%H%M%S")
        if m.group(2) and "Z" in blk[m.start():m.end() + 3]: d += datetime.timedelta(hours=5, minutes=30)
        if now - datetime.timedelta(hours=1) <= d <= now + datetime.timedelta(days=days): out.append((d, sm.group(1).strip()))
    out.sort()
    return "\n".join(f"{d.strftime('%a %d %b %I:%M %p')}: {t}" for d, t in out[:12]) or "Is dauran koi event nahi (repeating events yahan nahi dikhte)."

# =============================================================== face greeting (OpenCV, local, presence only)
_face = [False]
def _face_loop():
    import cv2
    det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    absent_since = time.time() - 9999; seen = False
    while True:
        try:
            cap = cv2.VideoCapture(0)
            ok, frame = cap.read(); cap.release()
            if ok:
                g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                present = len(det.detectMultiScale(g, 1.2, 6, minSize=(80, 80))) > 0
                if present:
                    if time.time() - absent_since > 20 * 60 and not seen:
                        h = time.localtime().tm_hour
                        _say(f"{'Suprabhat' if h < 12 else 'Namaste'} {config.USER_NAME}, wapas aa gaye! Kuch chahiye to bolo."); seen = True
                    absent_since = time.time() if seen and False else absent_since
                    last_seen[0] = time.time()
                else:
                    if time.time() - last_seen[0] > 120: absent_since = last_seen[0]; seen = False
        except Exception: pass
        time.sleep(3)
last_seen = [time.time()]
def face_greeting(action: str = "start") -> str:
    """Start or stop the webcam greeting: when a face appears after you were away 20+ minutes (or at startup), Jarvis greets you. Local OpenCV, no cloud, no photos saved. Needs opencv-python."""
    if action == "stop": _face[0] = False; return "Face greeting band (restart tak)."
    try: import cv2
    except Exception: return "Iske liye 'pip install opencv-python' chalao (install.bat dobara chalane se bhi ho jayega)."
    if _face[0]: return "Pehle se chal raha hai."
    _face[0] = True; last_seen[0] = time.time() - 9999; threading.Thread(target=_face_loop, daemon=True).start()
    return "Face greeting on. Camera sirf check karta hai ki koi saamne hai, photo save nahi hoti."

# =============================================================== deeper persistent memory (sqlite)
import sqlite3
_DB = DATA / "memory.db"
def _db():
    c = sqlite3.connect(_DB); c.execute("create table if not exists log(ts text, role text, text text)")
    c.execute("create table if not exists prefs(k text primary key, v text, ts text)"); return c
def log_turn(role, text):
    try:
        with _db() as c: c.execute("insert into log values(?,?,?)", (time.strftime("%Y-%m-%d %H:%M"), role, (text or "")[:1500]))
    except Exception: pass
def set_preference(key: str, value: str) -> str:
    """Remember a preference or fact about the user for good (survives restarts). Example key: 'favourite music', value: 'Arijit Singh'."""
    with _db() as c: c.execute("insert or replace into prefs values(?,?,?)", (key.lower().strip(), value, time.strftime("%Y-%m-%d")))
    return f"Yaad rakh liya: {key} = {value}."
def recall_past(query: str = "", limit: int = 8) -> str:
    """Search saved preferences and past conversations/work across sessions. Empty query = most recent."""
    with _db() as c:
        like = f"%{query.lower()}%"
        prefs = c.execute("select k,v from prefs where lower(k) like ? or lower(v) like ?", (like, like)).fetchall()
        rows = c.execute("select ts,role,text from log where lower(text) like ? order by rowid desc limit ?", (like, limit)).fetchall()
    out = [f"PREF {k}: {v}" for k, v in prefs] + [f"{t} {r}: {x[:160]}" for t, r, x in reversed(rows)]
    return "\n".join(out) or "Is baare me kuch yaad nahi."
def _prefs_text():
    try:
        with _db() as c: return "; ".join(f"{k}={v}" for k, v in c.execute("select k,v from prefs limit 30"))
    except Exception: return ""

EXTRA_TOOLS += [add_calendar_event, calendar_events, face_greeting, set_preference, recall_past]
_sb = start_background
def start_background():
    _sb()
    if os.getenv("FACE_GREETING", "false").strip().lower() in ("1", "true", "yes", "on"): face_greeting("start")
