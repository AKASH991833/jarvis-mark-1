"""All the things Jarvis can DO on the PC. Each public function is a tool for Gemini.
Dangerous ones call confirm() first - Jarvis asks you by voice/typing before acting."""
import os, sys, json, time, shutil, subprocess, threading, webbrowser, datetime, difflib, urllib.parse, urllib.request
from pathlib import Path
from . import config

# hooks set by main.py
confirm = lambda question: False          # ask user yes/no
notify = lambda text: print(text)         # speak something later (timers)
vision = lambda image_path, question: "Vision not available."
brain_reload = lambda: None
brain_status = lambda: "unknown"

IS_WIN = sys.platform.startswith("win")
HOME = Path.home()

def _p(path):
    """Expand ~, %VARS% and friendly names like Desktop/Downloads/Documents."""
    path = os.path.expandvars(os.path.expanduser(path.strip().strip('"')))
    friendly = {"desktop": "Desktop", "downloads": "Downloads", "documents": "Documents",
                "pictures": "Pictures", "music": "Music", "videos": "Videos"}
    parts = Path(path).parts
    if parts and parts[0].lower() in friendly and not Path(path).is_absolute():
        path = str(HOME / friendly[parts[0].lower()] / Path(*parts[1:]))
        if not os.path.exists(path) and (HOME / "OneDrive" / friendly[parts[0].lower()]).exists():
            path = str(HOME / "OneDrive" / friendly[parts[0].lower()] / Path(*parts[1:]))
    return path

# ---------------------------------------------------------------- apps & web
APPS = {
    "notepad": "notepad", "calculator": "calc", "calc": "calc", "paint": "mspaint",
    "cmd": "cmd", "command prompt": "cmd", "powershell": "powershell",
    "file explorer": "explorer", "explorer": "explorer", "task manager": "taskmgr",
    "control panel": "control", "settings": "ms-settings:", "chrome": "chrome",
    "google chrome": "chrome", "edge": "msedge", "firefox": "firefox",
    "vscode": "code", "vs code": "code", "visual studio code": "code",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "snipping tool": "snippingtool", "camera": "microsoft.windows.camera:",
    "spotify": "spotify", "whatsapp": "whatsapp:", "vlc": "vlc", "terminal": "wt",
}

def _find_start_menu(name):
    roots = [Path(os.environ.get("ProgramData", "C:/ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
             Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs"]
    names = {}
    for r in roots:
        if r.exists():
            for f in r.rglob("*.lnk"):
                names[f.stem.lower()] = f
    m = difflib.get_close_matches(name.lower(), list(names), n=1, cutoff=0.6)
    if not m:
        m = [n for n in names if name.lower() in n][:1]
    return names[m[0]] if m else None

def open_app(name: str) -> str:
    """Open an application by name, e.g. 'chrome', 'notepad', 'calculator', 'vs code', 'spotify'."""
    key = name.lower().strip()
    try:
        if not IS_WIN:
            subprocess.Popen([key]); return f"Opened {name}"
        target = APPS.get(key)
        if target:
            subprocess.Popen(f'start "" "{target}"' if ":" in target else f'start "" {target}', shell=True)
            return f"Opened {name}"
        lnk = _find_start_menu(key)
        if lnk:
            os.startfile(str(lnk)); return f"Opened {lnk.stem}"
        subprocess.Popen(f'start "" "{name}"', shell=True)
        return f"Tried to open {name} (not sure it exists)"
    except Exception as e:
        return f"Could not open {name}: {e}"

def close_app(process_name: str) -> str:
    """Close a running app by process name, e.g. 'chrome' or 'notepad'. Asks permission first."""
    if not confirm(f"{process_name} band kar doon?"):
        return "User said no."
    import psutil
    n = 0
    for p in psutil.process_iter(["name"]):
        if process_name.lower().replace(".exe", "") in (p.info["name"] or "").lower():
            try: p.terminate(); n += 1
            except Exception: pass
    return f"Closed {n} process(es) matching {process_name}"

def open_website(url: str) -> str:
    """Open a website in the default browser. Accepts 'youtube.com' or a full URL."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url); return f"Opened {url}"

def google_search(query: str) -> str:
    """Search Google in the browser."""
    webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(query))
    return f"Searched Google for: {query}"

def youtube_search(query: str) -> str:
    """Search YouTube in the browser (for songs, videos, tutorials)."""
    webbrowser.open("https://www.youtube.com/results?search_query=" + urllib.parse.quote(query))
    return f"Opened YouTube search for: {query}"

def play_on_youtube(query: str) -> str:
    """Find the first YouTube result for the query and play it directly."""
    try:
        req = urllib.request.Request("https://www.youtube.com/results?search_query=" + urllib.parse.quote(query),
                                     headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "ignore")
        import re
        ids = re.findall(r'"videoId":"([\w-]{11})"', html)
        if ids:
            webbrowser.open("https://www.youtube.com/watch?v=" + ids[0])
            return f"Playing first YouTube result for {query}"
    except Exception:
        pass
    return youtube_search(query)

def open_gmail() -> str:
    """Open Gmail inbox in the browser (uses his already logged-in Chrome/Edge)."""
    webbrowser.open("https://mail.google.com"); return "Opened Gmail"

def get_weather(city: str = "Mumbai") -> str:
    """Current weather for a city."""
    try:
        r = urllib.request.urlopen("https://wttr.in/" + urllib.parse.quote(city) + "?format=%l:+%C,+%t,+humidity+%h,+wind+%w", timeout=10)
        return r.read().decode()
    except Exception as e:
        return f"Weather unavailable: {e}"

# ---------------------------------------------------------------- files
def open_path(path: str) -> str:
    """Open any file or folder with its default program (e.g. 'Downloads', 'Desktop/report.pdf', 'D:\\\\')."""
    p = _p(path)
    if not os.path.exists(p):
        return f"Not found: {p}"
    if IS_WIN: os.startfile(p)
    else: subprocess.Popen(["xdg-open", p])
    return f"Opened {p}"

def list_folder(path: str = "Desktop", limit: int = 60) -> str:
    """List files and folders inside a folder."""
    p = _p(path)
    if not os.path.isdir(p): return f"Not a folder: {p}"
    items = sorted(os.listdir(p))
    out = []
    for n in items[:limit]:
        full = os.path.join(p, n)
        out.append(("[DIR] " if os.path.isdir(full) else "") + n)
    return f"{p} ({len(items)} items):\n" + "\n".join(out)

def find_files(name_contains: str, folder: str = "~", limit: int = 25) -> str:
    """Search for files whose name contains the text, inside a folder (default: whole home folder)."""
    root = _p(folder); hits = []
    q = name_contains.lower()
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if not d.startswith(".") and d.lower() not in ("appdata", "node_modules", "$recycle.bin")]
        for f in fn:
            if q in f.lower():
                hits.append(os.path.join(dp, f))
                if len(hits) >= limit: return "\n".join(hits)
    return "\n".join(hits) or "No files found."

def read_text_file(path: str, max_chars: int = 6000) -> str:
    """Read a text file (txt, py, csv, md, json, log...)."""
    p = _p(path)
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")[:max_chars]
    except Exception as e:
        return f"Cannot read: {e}"

def write_text_file(path: str, content: str, append: bool = False) -> str:
    """Create or write a text file. Asks permission if the file already exists."""
    p = _p(path)
    if os.path.exists(p) and not append and not confirm(f"{os.path.basename(p)} pehle se hai. Overwrite karoon?"):
        return "User said no."
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "a" if append else "w", encoding="utf-8") as f: f.write(content)
    return f"Saved {p}"

def create_folder(path: str) -> str:
    """Create a folder (and parents)."""
    p = _p(path); os.makedirs(p, exist_ok=True); return f"Created {p}"

def copy_path(src: str, dst: str) -> str:
    """Copy a file or folder."""
    s, d = _p(src), _p(dst)
    if os.path.isdir(s): shutil.copytree(s, os.path.join(d, os.path.basename(s)) if os.path.isdir(d) else d)
    else: shutil.copy2(s, d)
    return f"Copied {s} to {d}"

def move_path(src: str, dst: str) -> str:
    """Move or rename a file or folder. Asks permission first."""
    s, d = _p(src), _p(dst)
    if not confirm(f"{os.path.basename(s)} ko move karoon?"): return "User said no."
    shutil.move(s, d); return f"Moved {s} to {d}"

def delete_path(path: str) -> str:
    """Delete a file or folder (goes to Recycle Bin so it can be restored). ALWAYS asks permission first."""
    p = _p(path)
    if not os.path.exists(p): return f"Not found: {p}"
    if not confirm(f"{os.path.basename(p)} delete kar doon? Ye Recycle Bin me jayega."):
        return "User said no. Nothing deleted."
    from send2trash import send2trash
    send2trash(p); return f"Moved to Recycle Bin: {p}"

# ---------------------------------------------------------------- screen / keyboard / mouse
def take_screenshot() -> str:
    """Take a screenshot and save it in Pictures/Jarvis."""
    import pyautogui
    config.SHOT_DIR.mkdir(parents=True, exist_ok=True)
    f = config.SHOT_DIR / time.strftime("screenshot_%Y%m%d_%H%M%S.png")
    pyautogui.screenshot().save(f); return f"Screenshot saved: {f}"

def describe_screen(question: str = "What is on the screen? Describe briefly.") -> str:
    """Look at the screen right now (vision) and answer a question about it."""
    import pyautogui
    f = Path(os.environ.get("TEMP", "/tmp")) / "jarvis_screen.png"
    pyautogui.screenshot().save(f)
    return vision(str(f), question)

def type_text(text: str) -> str:
    """Type text into whatever window is currently focused (supports Hindi via clipboard paste)."""
    import pyautogui, pyperclip
    old = None
    try: old = pyperclip.paste()
    except Exception: pass
    pyperclip.copy(text); time.sleep(0.15)
    pyautogui.hotkey("ctrl", "v"); time.sleep(0.2)
    if old is not None: pyperclip.copy(old)
    return "Typed."

def press_keys(keys: str) -> str:
    """Press a key or shortcut, e.g. 'enter', 'ctrl+s', 'alt+tab', 'win+d', 'ctrl+shift+esc'."""
    import pyautogui
    pyautogui.hotkey(*[k.strip() for k in keys.lower().split("+")]); return f"Pressed {keys}"

def click_at(x: int, y: int, double: bool = False) -> str:
    """Click the mouse at screen coordinates."""
    import pyautogui
    (pyautogui.doubleClick if double else pyautogui.click)(x, y); return "Clicked."

def scroll(amount: int) -> str:
    """Scroll the page. Positive = up, negative = down."""
    import pyautogui
    pyautogui.scroll(amount); return "Scrolled."

def get_clipboard() -> str:
    """Read what is currently copied in the clipboard."""
    import pyperclip; return pyperclip.paste()

def set_clipboard(text: str) -> str:
    """Copy text to the clipboard."""
    import pyperclip; pyperclip.copy(text); return "Copied to clipboard."

# ---------------------------------------------------------------- system
def system_info() -> str:
    """CPU, RAM, disk, battery and uptime of this PC."""
    import psutil
    b = psutil.sensors_battery()
    d = shutil.disk_usage(os.path.abspath(os.sep))
    up = datetime.timedelta(seconds=int(time.time() - psutil.boot_time()))
    return (f"CPU {psutil.cpu_percent(interval=0.5)}%, RAM {psutil.virtual_memory().percent}% used, "
            f"Disk {d.used // 2**30}/{d.total // 2**30} GB used, "
            + (f"Battery {int(b.percent)}%{' charging' if b.power_plugged else ''}, " if b else "")
            + f"Uptime {up}")

def current_time() -> str:
    """Current date and time."""
    return datetime.datetime.now().strftime("%A, %d %B %Y, %I:%M %p")

def volume(action: str, level: int = 10) -> str:
    """Change volume. action = up | down | mute | set. For 'up'/'down', level is number of steps (each ~2%). For 'set', level is 0-100."""
    import pyautogui
    a = action.lower()
    if a == "mute": pyautogui.press("volumemute"); return "Mute toggled."
    if a == "set":
        for _ in range(50): pyautogui.press("volumedown")
        for _ in range(max(0, min(100, level)) // 2): pyautogui.press("volumeup")
        return f"Volume about {level}%."
    key = "volumeup" if a == "up" else "volumedown"
    for _ in range(max(1, level)): pyautogui.press(key)
    return f"Volume {a}."

def brightness(level: int) -> str:
    """Set screen brightness 0-100 (laptops)."""
    cmd = f'powershell -NoProfile -Command "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{int(level)})"'
    subprocess.run(cmd, shell=True, capture_output=True, timeout=20); return f"Brightness {level}%"

def media_control(action: str) -> str:
    """Media keys: play_pause | next | previous."""
    import pyautogui
    pyautogui.press({"play_pause": "playpause", "next": "nexttrack", "previous": "prevtrack"}.get(action, "playpause")); return "Done."

SAFE_CMDS = ("dir", "ipconfig", "whoami", "hostname", "systeminfo", "ver", "echo", "tasklist", "ping", "date /t", "time /t", "where", "type ", "tree", "netstat", "wmic cpu", "python --version", "pip list", "git status", "git log")

def run_shell_command(command: str) -> str:
    """Run a Windows command (cmd/PowerShell syntax) and return its output. Asks permission unless it is a harmless read-only command."""
    c = command.strip()
    if not c.lower().startswith(SAFE_CMDS) and not confirm(f"Ye command chalaoon? {c[:120]}"):
        return "User said no. Command not run."
    try:
        r = subprocess.run(c, shell=True, capture_output=True, timeout=90, text=True, errors="replace")
        return ((r.stdout or "") + (r.stderr or ""))[:3500] or f"Done (exit code {r.returncode})"
    except subprocess.TimeoutExpired:
        return "Command timed out after 90 seconds."

def power(action: str) -> str:
    """Power actions: lock | sleep | shutdown | restart | logoff. All except lock ask permission first."""
    a = action.lower()
    if a == "lock":
        subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True); return "Locked."
    if not confirm(f"PC {a} kar doon?"): return "User said no."
    cmds = {"shutdown": "shutdown /s /t 10", "restart": "shutdown /r /t 10", "logoff": "shutdown /l",
            "sleep": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0"}
    if a not in cmds: return "Unknown power action."
    subprocess.run(cmds[a], shell=True); return f"{a} started. (cancel with: shutdown /a)"

# ---------------------------------------------------------------- memory, timers
def remember(fact: str) -> str:
    """Save a fact about the user for the future (name of friend, preference, etc.)."""
    data = json.loads(config.MEMORY_FILE.read_text("utf-8")) if config.MEMORY_FILE.exists() else []
    data.append({"fact": fact, "date": time.strftime("%Y-%m-%d")})
    config.MEMORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8"); return "Remembered."

def load_memory() -> str:
    if config.MEMORY_FILE.exists():
        try: return "\n".join("- " + d["fact"] for d in json.loads(config.MEMORY_FILE.read_text("utf-8"))[-40:])
        except Exception: pass
    return ""

def set_reminder(minutes: float, message: str) -> str:
    """Remind the user (by voice) after N minutes. Works as a timer too."""
    threading.Timer(minutes * 60, lambda: notify(f"Reminder: {message}")).start()
    return f"Reminder set for {minutes} minutes: {message}"

# ---------------------------------------------------------------- messaging / email (always confirm)
def send_whatsapp(phone_with_country_code: str, message: str) -> str:
    """Send a WhatsApp message via WhatsApp Web / desktop (best effort). Always asks permission first. Phone like 919876543210."""
    if not confirm(f"{phone_with_country_code} ko WhatsApp bhejun: {message[:100]} ?"): return "User said no. Not sent."
    import pyautogui
    webbrowser.open(f"https://web.whatsapp.com/send?phone={phone_with_country_code}&text={urllib.parse.quote(message)}")
    time.sleep(18); pyautogui.press("enter")
    return "Message sent via WhatsApp Web (if WhatsApp Web was logged in)."

def send_email(to: str, subject: str, body: str) -> str:
    """Send an email from the user's Gmail. Always asks permission first. Needs GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env."""
    if not (config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD):
        return "Gmail is not set up. Add GMAIL_ADDRESS and GMAIL_APP_PASSWORD in the .env file (see README step 7)."
    if not confirm(f"{to} ko email bhejun? Subject: {subject}"): return "User said no. Not sent."
    import smtplib; from email.message import EmailMessage
    m = EmailMessage(); m["From"], m["To"], m["Subject"] = config.GMAIL_ADDRESS, to, subject; m.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD); s.send_message(m)
    return "Email sent."

def read_emails(count: int = 5, unread_only: bool = True) -> str:
    """Read the latest emails (sender, subject, short preview) from Gmail. Needs GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env."""
    if not (config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD):
        return "Gmail is not set up. Add GMAIL_ADDRESS and GMAIL_APP_PASSWORD in the .env file (see README step 7). Meanwhile I can open Gmail in the browser."
    import imaplib, email
    from email.header import decode_header, make_header
    M = imaplib.IMAP4_SSL("imap.gmail.com"); M.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD); M.select("INBOX", readonly=True)
    _, ids = M.search(None, "UNSEEN" if unread_only else "ALL")
    out = []
    for i in ids[0].split()[-count:][::-1]:
        _, d = M.fetch(i, "(RFC822)"); msg = email.message_from_bytes(d[0][1])
        body = ""
        for part in (msg.walk() if msg.is_multipart() else [msg]):
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")[:200]; break
        out.append(f"From: {make_header(decode_header(msg['From']))} | Subject: {make_header(decode_header(msg['Subject'] or ''))} | {body.strip()}")
    M.logout(); return "\n".join(out) or "No emails."


# ---------------------------------------------------------------- software install (winget = free, official Windows installer tool)
def _winget(args, timeout=120):
    r = subprocess.run("winget " + args, shell=True, capture_output=True, text=True, errors="replace", timeout=timeout)
    return (r.stdout or "") + (r.stderr or ""), r.returncode

def _winget_search(name):
    out, _ = _winget(f'search "{name}" --accept-source-agreements', 90)
    rows, started = [], False
    for ln in out.splitlines():
        if set(ln.strip()) == {"-"} and len(ln.strip()) > 10: started = True; continue
        if started and ln.strip():
            parts = [x for x in __import__("re").split(r"\s{2,}", ln.strip()) if x]
            if len(parts) >= 2: rows.append((parts[0], parts[1]))
    return rows

def install_software(name: str) -> str:
    """Download and install a program (e.g. 'VLC', 'Chrome', 'VS Code', 'WhatsApp', '7zip', 'Python') using Windows winget (free, official). Searches, asks permission, installs silently, then VERIFIES it is installed. Windows may show a 'Yes/No' admin prompt - the user must click Yes."""
    if not IS_WIN: return "Install works only on Windows."
    try:
        if _winget("--version", 20)[1] != 0: return "winget is missing. Open Microsoft Store, update 'App Installer', then try again. Or use download_file with the official download link."
        rows = _winget_search(name)
        if not rows: return f"winget could not find '{name}'. Try a different name or use download_file with the official link."
        # prefer exact/closest name
        low = name.lower()
        best = next((r for r in rows if r[0].lower() == low), None) or next((r for r in rows if low in r[0].lower()), rows[0])
        if not confirm(f"{best[0]} install kar doon? Ye free hai. Agar Windows poochhe to Yes dabana."):
            return "User said no. Not installed."
        out, rc = _winget(f'install --id "{best[1]}" -e --silent --accept-package-agreements --accept-source-agreements', 1200)
        chk, _ = _winget(f'list --id "{best[1]}" -e --accept-source-agreements', 60)
        if best[1].lower() in chk.lower():
            return f"VERIFIED: {best[0]} ({best[1]}) is installed."
        return f"Install may have failed (code {rc}). Output tail: {out[-700:]}"
    except subprocess.TimeoutExpired:
        return "Install took too long and was stopped."

def uninstall_software(name: str) -> str:
    """Uninstall a program with winget. Always asks permission first."""
    if not confirm(f"{name} uninstall kar doon?"): return "User said no."
    out, rc = _winget(f'uninstall "{name}" --silent --accept-source-agreements', 900)
    return out[-600:] or f"Done (code {rc})"

def list_installed(filter_text: str = "") -> str:
    """List installed programs (optionally filtered by name)."""
    out, _ = _winget(f'list "{filter_text}" --accept-source-agreements' if filter_text else "list --accept-source-agreements", 90)
    return out[-3500:]

def download_file(url: str, filename: str = "") -> str:
    """Download a file from a link into the Downloads folder (for software not on winget). Returns the saved path. Only use official links."""
    import requests
    name = filename or os.path.basename(urllib.parse.urlparse(url).path) or "download.bin"
    dest = HOME / "Downloads" / name
    if not confirm(f"{url[:80]} se {name} download karoon?"): return "User said no."
    with requests.get(url, stream=True, timeout=60, headers={"User-Agent": "Mozilla/5.0"}) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20): f.write(chunk)
    return f"Downloaded to {dest} ({dest.stat().st_size // 1024} KB)"

def run_installer(path: str, silent_flags: str = "") -> str:
    """Run a downloaded installer (.exe or .msi). Optionally pass silent flags like '/S' or '/VERYSILENT'. Asks permission first. Afterwards use gui_task to click through any wizard."""
    p = _p(path)
    if not os.path.exists(p): return f"Not found: {p}"
    if not confirm(f"{os.path.basename(p)} installer chalaoon?"): return "User said no."
    cmd = f'msiexec /i "{p}" /qn' if p.lower().endswith(".msi") and not silent_flags else f'"{p}" {silent_flags}'
    try:
        if silent_flags or p.lower().endswith(".msi"):
            r = subprocess.run(cmd, shell=True, timeout=900, capture_output=True, text=True, errors="replace")
            return f"Installer finished with code {r.returncode}. Now verify the program is installed."
        os.startfile(p); return "Installer window opened. Use gui_task to click Next/Install if needed, then verify."
    except Exception as e:
        return f"Installer problem: {e}"

def check_program_installed(name: str) -> str:
    """Check whether a program is installed / available (winget list, PATH and Start Menu)."""
    out, _ = _winget(f'list "{name}" --accept-source-agreements', 60) if IS_WIN else ("", 1)
    found = [l for l in out.splitlines() if name.lower() in l.lower()]
    lnk = _find_start_menu(name) if IS_WIN else None
    return ("Installed: " + "; ".join(x.strip()[:80] for x in found[:3])) if found else (f"Start Menu shortcut found: {lnk.stem}" if lnk else (f"On PATH: {shutil.which(name)}" if shutil.which(name) else "Not found."))

# ---------------------------------------------------------------- human-like GUI control (vision loop)
STOP_WORDS = ("delete", "remove", "uninstall", "format", "pay", "purchase", "buy", "send", "submit", "confirm order", "sign out", "shutdown", "password")

def _screen_json(question):
    import pyautogui, re
    f = Path(os.environ.get("TEMP", "/tmp")) / "jarvis_gui.png"
    img = pyautogui.screenshot(); img.save(f)
    txt = vision(str(f), question)
    m = re.search(r"\{.*\}", txt, re.S)
    return json.loads(m.group(0)) if m else {}, img.size

def _locked():
    from . import bus
    return bus.locked

def find_and_click(description: str, double: bool = False) -> str:
    """Look at the screen, find the button/icon/text described (e.g. 'the Next button', 'Chrome icon on taskbar') and click it like a human."""
    if _locked(): return "PC control is LOCKED by the user."
    import pyautogui
    d, (w, h) = _screen_json(f'Find this UI element on the screen: "{description}". Reply ONLY JSON: {{"found": true/false, "x": 0-1000, "y": 0-1000}} where x,y are the CENTER of the element as thousandths of the screen width/height.')
    if not d.get("found"): return f"Could not see '{description}' on screen."
    x, y = int(d["x"] / 1000 * w), int(d["y"] / 1000 * h)
    (pyautogui.doubleClick if double else pyautogui.click)(x, y); return f"Clicked {description} at {x},{y}."

def gui_task(goal: str, max_steps: int = 14) -> str:
    """Do a multi-step task on screen like a human: it looks at the screen, clicks, types and presses keys step by step until the goal is done (e.g. 'click through the installer wizard', 'in Settings turn on dark mode'). Asks permission first, and again before any risky step. Move the mouse to a screen corner to emergency-stop."""
    if _locked(): return "PC control is LOCKED by the user."
    if not confirm(f"Main screen dekhkar mouse aur keyboard khud chalaoonga: {goal[:90]}. Theek hai?"): return "User said no."
    import pyautogui
    history = []
    for step in range(max_steps):
        if _locked(): return "Stopped: PC control was locked."
        q = (f'You control a Windows PC like a human. GOAL: "{goal}". Steps done so far: {history[-6:] or "none"}. '
             'Look at the screenshot and choose ONE next action. Reply ONLY JSON: '
             '{"action":"click|double_click|type|key|scroll|wait|done|fail","x":0-1000,"y":0-1000,"text":"","keys":"enter or ctrl+s etc","amount":-5,"what":"short description of the target","risky":true/false}. '
             'x,y are thousandths of screen width/height. Use "done" when the goal is complete, "fail" if impossible. risky=true for delete/uninstall/payment/sending/password actions.')
        try:
            d, (w, h) = _screen_json(q)
        except Exception as e:
            return f"Vision problem: {e}"
        a = (d.get("action") or "fail").lower(); what = d.get("what", "")
        if a == "done": return f"Done: {goal}. Steps taken: {len(history)}."
        if a == "fail": return f"Could not finish: {what}. Steps taken: {len(history)}."
        if d.get("risky") or any(s in what.lower() for s in STOP_WORDS):
            if not confirm(f"Risky step: {what}. Karoon?"): return "Stopped by user at a risky step."
        try:
            if a in ("click", "double_click"):
                x, y = int(d["x"] / 1000 * w), int(d["y"] / 1000 * h)
                (pyautogui.doubleClick if a == "double_click" else pyautogui.click)(x, y)
            elif a == "type": type_text(d.get("text", ""))
            elif a == "key": press_keys(d.get("keys", "enter"))
            elif a == "scroll": pyautogui.scroll(int(d.get("amount", -5)) * 100)
            elif a == "wait": time.sleep(3)
        except Exception as e:
            return f"Action failed: {e}"
        history.append(f"{a}: {what}"); time.sleep(1.4)
    return f"Reached step limit ({max_steps}). Last steps: {history[-3:]}"

def list_windows() -> str:
    """List the titles of open windows."""
    try:
        import pygetwindow as gw
        return "\n".join(sorted({w.title for w in gw.getAllWindows() if w.title.strip()})[:40])
    except Exception as e:
        return f"Not available: {e}"

def focus_window(title_contains: str) -> str:
    """Bring a window to the front by part of its title (e.g. 'Chrome', 'Notepad')."""
    try:
        import pygetwindow as gw
        ws = [w for w in gw.getAllWindows() if title_contains.lower() in w.title.lower() and w.title.strip()]
        if not ws: return "No such window."
        w = ws[0]
        if w.isMinimized: w.restore()
        w.activate(); return f"Focused: {w.title}"
    except Exception as e:
        return f"Could not focus: {e}"

def window_action(title_contains: str, action: str) -> str:
    """Minimize, maximize, restore or close a window by part of its title. action = minimize | maximize | restore | close (close asks permission)."""
    try:
        import pygetwindow as gw
        ws = [w for w in gw.getAllWindows() if title_contains.lower() in w.title.lower() and w.title.strip()]
        if not ws: return "No such window."
        w = ws[0]
        if action == "close":
            if not confirm(f"{w.title[:40]} window band karoon?"): return "User said no."
            w.close()
        else: getattr(w, action)()
        return f"{action} done: {w.title}"
    except Exception as e:
        return f"Window action failed: {e}"

def show_desktop() -> str:
    """Minimize everything and show the desktop."""
    import pyautogui; pyautogui.hotkey("win", "d"); return "Desktop shown."

# ---------------------------------------------------------------- knowledge, notes, routines, housekeeping
def get_news(topic: str = "India", count: int = 6) -> str:
    """Latest news headlines (Google News RSS, free)."""
    import re
    try:
        url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(topic) + "&hl=en-IN&gl=IN&ceid=IN:en"
        x = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=12).read().decode("utf-8", "ignore")
        return "\n".join(re.findall(r"<item>.*?<title>(.*?)</title>", x, re.S)[:count]) or "No news."
    except Exception as e:
        return f"News unavailable: {e}"

def wikipedia_summary(topic: str, lang: str = "en") -> str:
    """Short factual summary of a topic from Wikipedia (free)."""
    try:
        r = urllib.request.urlopen(urllib.request.Request(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(topic), headers={"User-Agent": "Jarvis"}), timeout=12)
        return json.loads(r.read().decode()).get("extract", "Nothing found.")
    except Exception as e:
        return f"Not found: {e}"

def read_webpage(url: str, max_chars: int = 5000) -> str:
    """Download a web page and return its readable text (to summarize or answer questions)."""
    import re
    try:
        h = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read().decode("utf-8", "ignore")
        h = re.sub(r"(?s)<(script|style).*?</\1>", " ", h); h = re.sub(r"<[^>]+>", " ", h)
        return re.sub(r"\s+", " ", h)[:max_chars]
    except Exception as e:
        return f"Could not read page: {e}"

NOTES = config.DATA_DIR / "notes.txt"
def add_note(text: str) -> str:
    """Save a note."""
    with open(NOTES, "a", encoding="utf-8") as f: f.write(time.strftime("[%d %b %H:%M] ") + text + "\n")
    return "Note saved."

def read_notes(last: int = 15) -> str:
    """Read saved notes."""
    return "".join(NOTES.read_text("utf-8").splitlines(True)[-last:]) if NOTES.exists() else "No notes yet."

ROUTINES = config.DATA_DIR / "routines.json"
DEFAULT_ROUTINES = {"morning": ["https://mail.google.com", "https://news.google.com", "https://www.youtube.com"],
                    "work": ["code", "chrome"], "study": ["https://www.youtube.com", "notepad"]}

def save_routine(name: str, items_comma_separated: str) -> str:
    """Create/replace a routine: a named list of apps and websites that open together, e.g. name='study', items='chrome, youtube.com, notepad'."""
    d = json.loads(ROUTINES.read_text("utf-8")) if ROUTINES.exists() else dict(DEFAULT_ROUTINES)
    d[name.lower()] = [x.strip() for x in items_comma_separated.split(",") if x.strip()]
    ROUTINES.write_text(json.dumps(d, indent=1), "utf-8"); return f"Routine '{name}' saved."

def run_routine(name: str) -> str:
    """Run a saved routine (e.g. 'morning', 'work', 'study'): opens all its apps and sites."""
    d = json.loads(ROUTINES.read_text("utf-8")) if ROUTINES.exists() else DEFAULT_ROUTINES
    items = d.get(name.lower().replace(" routine", "").strip())
    if not items: return "No such routine. Available: " + ", ".join(d)
    for it in items:
        (open_website if ("." in it and " " not in it) else open_app)(it); time.sleep(0.8)
    return f"Routine {name} started: {', '.join(items)}"

def top_processes(count: int = 6) -> str:
    """Show the programs using the most memory right now."""
    import psutil
    ps = sorted(psutil.process_iter(["name", "memory_percent"]), key=lambda p: p.info["memory_percent"] or 0, reverse=True)[:count]
    return "\n".join(f"{p.info['name']}: {p.info['memory_percent']:.1f}% RAM" for p in ps)

def network_info() -> str:
    """Wi-Fi/internet info: local IP and whether internet works."""
    import socket
    try: ip = socket.gethostbyname(socket.gethostname())
    except Exception: ip = "unknown"
    try: urllib.request.urlopen("https://www.google.com", timeout=5); net = "Internet OK"
    except Exception: net = "No internet"
    return f"{net}. Local IP {ip}."

def clean_temp_files() -> str:
    """Delete temporary files in the Windows temp folder to free space. Asks permission first."""
    tmp = os.environ.get("TEMP", "/tmp")
    if not confirm("Temp files saaf kar doon? Ye safe hai."): return "User said no."
    n = freed = 0
    for f in Path(tmp).iterdir():
        try:
            s = f.stat().st_size if f.is_file() else 0
            shutil.rmtree(f) if f.is_dir() else f.unlink(); n += 1; freed += s
        except Exception: pass
    return f"Removed {n} items, freed about {freed // 2**20} MB (in-use files skipped)."

def organize_folder(path: str = "Downloads") -> str:
    """Sort loose files in a folder into subfolders by type (Images, Documents, Videos, Music, Archives, Programs). Asks permission first. Nothing is deleted."""
    p = _p(path)
    kinds = {"Images": (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"), "Documents": (".pdf", ".doc", ".docx", ".txt", ".ppt", ".pptx", ".xls", ".xlsx", ".csv"),
             "Videos": (".mp4", ".mkv", ".avi", ".mov"), "Music": (".mp3", ".wav", ".m4a"), "Archives": (".zip", ".rar", ".7z"), "Programs": (".exe", ".msi", ".apk")}
    if not confirm(f"{os.path.basename(p)} folder ki files type ke hisaab se arrange kar doon?"): return "User said no."
    n = 0
    for f in Path(p).iterdir():
        if f.is_file():
            for k, ex in kinds.items():
                if f.suffix.lower() in ex:
                    (Path(p) / k).mkdir(exist_ok=True); shutil.move(str(f), str(Path(p) / k / f.name)); n += 1; break
    return f"Organized {n} files in {p}."

def open_settings_page(page: str = "") -> str:
    """Open a Windows Settings page: wifi, bluetooth, display, sound, apps, update, privacy, battery, or '' for main."""
    m = {"wifi": "network-wifi", "bluetooth": "bluetooth", "display": "display", "sound": "sound", "apps": "appsfeatures",
         "update": "windowsupdate", "privacy": "privacy", "battery": "batterysaver", "": ""}
    os.startfile(f"ms-settings:{m.get(page.lower(), page)}") if IS_WIN else None; return f"Opened settings {page}."

def set_alarm(time_24h: str, message: str = "Alarm") -> str:
    """Set an alarm at a clock time like '07:30' (today, or tomorrow if already passed). Jarvis must be running."""
    h, m = [int(x) for x in time_24h.split(":")[:2]]
    now = datetime.datetime.now(); tgt = now.replace(hour=h, minute=m, second=0)
    if tgt <= now: tgt += datetime.timedelta(days=1)
    return set_reminder((tgt - now).total_seconds() / 60, message) + f" (at {tgt.strftime('%d %b %H:%M')})"


# ---------------------------------------------------------------- self-upgrade: local brain (Ollama), research
import re as _re
def system_specs() -> str:
    """Detect this PC's RAM, CPU, graphics card and free disk space (used to pick a local AI model)."""
    import psutil
    ram = psutil.virtual_memory().total / 2**30
    gpu = ""
    if IS_WIN:
        try: gpu = subprocess.run("wmic path win32_VideoController get name", shell=True, capture_output=True, text=True, timeout=20).stdout.replace("Name", "").strip().replace("\n", "; ")
        except Exception: pass
    free = shutil.disk_usage(os.path.abspath(os.sep)).free / 2**30
    return f"RAM {ram:.1f} GB, CPU cores {psutil.cpu_count(logical=False) or psutil.cpu_count()}, GPU: {gpu or 'unknown'}, free disk {free:.0f} GB"

def _pick_model():
    import psutil
    ram = psutil.virtual_memory().total / 2**30
    if ram < 5.5: return "llama3.2:1b", 1.3
    if ram < 9: return "llama3.2:3b", 2.0
    if ram < 15: return "qwen2.5:7b", 4.7
    return "llama3.1:8b", 4.9

def _ollama_exe():
    p = shutil.which("ollama")
    if p: return p
    c = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return str(c) if c.exists() else None

def _ollama_up(url):
    try: urllib.request.urlopen(url + "/api/tags", timeout=3); return True
    except Exception: return False

def upgrade_brain_to_local(model: str = "") -> str:
    """Give Jarvis a free offline brain: installs Ollama (if missing), checks this PC's specs, picks a model that fits (small Llama for low RAM), downloads it, and enables automatic switching when Gemini free limit ends. Asks permission first. Uses disk space and takes several minutes."""
    from . import settings
    import requests
    s = settings.load(); url = s["ollama_url"]
    pick, gb = (model, 3.0) if model else _pick_model()
    specs = system_specs()
    free = shutil.disk_usage(os.path.abspath(os.sep)).free / 2**30
    if free < gb + 3: return f"Not enough disk space ({free:.0f} GB free, need about {gb + 3:.0f} GB). Free some space first. Specs: {specs}"
    if not confirm(f"Tumhare PC ({specs[:60]}) ke liye {pick} model theek rahega, lagbhag {gb} GB download. Ollama bhi install hoga. Free hai. Shuru karoon?"):
        return "User said no."
    if not _ollama_exe() and not _ollama_up(url):
        r = install_software("Ollama")
        if "VERIFIED" not in r and not _ollama_exe(): return "Ollama install did not finish: " + r
    if not _ollama_up(url):
        exe = _ollama_exe()
        if not exe: return "Ollama installed but not found. Restart the PC once and ask me again."
        subprocess.Popen([exe, "serve"], creationflags=0x08000000 if IS_WIN else 0)
        for _ in range(30):
            time.sleep(1)
            if _ollama_up(url): break
        else: return "Ollama server did not start."
    from . import bus
    bus.log("info", f"Downloading local model {pick} ...")
    last = 0
    with requests.post(url + "/api/pull", json={"name": pick}, stream=True, timeout=3600) as r:
        for line in r.iter_lines():
            if not line: continue
            d = json.loads(line)
            if d.get("total") and time.time() - last > 15:
                last = time.time(); bus.log("info", f"{pick}: {d['completed'] * 100 // d['total']}%")
            if d.get("error"): return "Download error: " + d["error"]
    tags = requests.get(url + "/api/tags", timeout=10).json().get("models", [])
    if not any(t["name"].startswith(pick.split(":")[0]) for t in tags): return "Model download could not be verified."
    settings.save(ollama_model=pick, backend="auto"); brain_reload()
    return f"VERIFIED: local brain {pick} is ready. Jarvis now uses Gemini first and switches to the local brain automatically when the Gemini free limit ends, then comes back. (Local small models are weaker at Hindi.)"

def set_brain_mode(mode: str) -> str:
    """Choose the brain: 'gemini' (cloud only), 'ollama' (local offline only) or 'auto' (Gemini first, local when the free limit ends)."""
    from . import settings
    mode = mode.lower().strip()
    if mode not in ("gemini", "ollama", "auto"): return "Mode must be gemini, ollama or auto."
    settings.save(backend=mode); brain_reload(); return f"Brain mode set to {mode}."

def brain_status_report() -> str:
    """Tell which brain (Gemini or local Ollama) is active and whether the local model is ready."""
    return brain_status()
brain_status_report.__name__ = "brain_status"

def _get_json(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Jarvis", "Accept": "application/json"}), timeout=15).read().decode())

def research_upgrades(topic: str = "") -> str:
    """Research mode: search free public sources (GitHub, Hacker News, Ollama library) for new FREE tools, AI models and ideas that could improve Jarvis or help the user's work. Returns suggestions only. NEVER installs anything; the user decides."""
    topic = topic.strip() or "voice assistant python free local LLM"
    out = []
    since = (datetime.date.today() - datetime.timedelta(days=180)).isoformat()
    try:
        d = _get_json("https://api.github.com/search/repositories?q=" + urllib.parse.quote(f"{topic} pushed:>{since}") + "&sort=stars&order=desc&per_page=6")
        out.append("GITHUB (recent, popular):")
        out += [f"- {i['full_name']} ({i['stargazers_count']} stars): {(i.get('description') or '')[:110]} | {i['html_url']} | license: {(i.get('license') or {}).get('spdx_id', 'unknown')}" for i in d.get("items", [])]
    except Exception as e: out.append(f"GitHub unavailable: {e}")
    try:
        ts = int(time.time()) - 90 * 86400
        d = _get_json("https://hn.algolia.com/api/v1/search?tags=story&query=" + urllib.parse.quote(topic) + f"&numericFilters=created_at_i>{ts}&hitsPerPage=5")
        out.append("HACKER NEWS (last 90 days):")
        out += [f"- {h['title']} ({h.get('points', 0)} pts) {h.get('url') or ''}" for h in d.get("hits", [])]
    except Exception as e: out.append(f"HN unavailable: {e}")
    try:
        h = urllib.request.urlopen(urllib.request.Request("https://ollama.com/library", headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read().decode("utf-8", "ignore")
        names = list(dict.fromkeys(_re.findall(r'href="/library/([\w.\-]+)"', h)))[:12]
        out.append("OLLAMA LIBRARY (free local models, newest/popular first): " + ", ".join(names))
    except Exception as e: out.append(f"Ollama library unavailable: {e}")
    out.append("NOTE: these are only suggestions. Check licenses/safety, and ask the user before installing anything.")
    return "\n".join(out)

_RAW = [open_app, close_app, open_website, google_search, youtube_search, play_on_youtube, open_gmail, get_weather,
        open_path, list_folder, find_files, read_text_file, write_text_file, create_folder, copy_path, move_path, delete_path,
        take_screenshot, describe_screen, type_text, press_keys, click_at, scroll, get_clipboard, set_clipboard,
        system_info, current_time, volume, brightness, media_control, run_shell_command, power,
        remember, set_reminder, send_whatsapp, send_email, read_emails,
        install_software, uninstall_software, list_installed, download_file, run_installer, check_program_installed,
        find_and_click, gui_task, list_windows, focus_window, window_action, show_desktop,
        get_news, wikipedia_summary, read_webpage, add_note, read_notes, save_routine, run_routine, top_processes,
        network_info, clean_temp_files, organize_folder, open_settings_page, set_alarm,
        system_specs, upgrade_brain_to_local, set_brain_mode, brain_status_report, research_upgrades]
from . import extras
_RAW += extras.EXTRA_TOOLS

AUDIT = config.DATA_DIR / "action_log.txt"
CONTROL = {"open_app", "close_app", "open_path", "delete_path", "move_path", "copy_path", "write_text_file", "type_text", "press_keys",
           "click_at", "scroll", "run_shell_command", "power", "install_software", "uninstall_software", "download_file", "run_installer",
           "dictation_mode", "meeting_mode", "music_control", "play_music", "create_new_tool", "self_heal", "undo_last_change", "apply_update", "save_skill", "run_skill", "find_and_click", "gui_task", "focus_window", "window_action", "show_desktop", "volume", "brightness", "media_control",
           "upgrade_brain_to_local", "clean_temp_files", "organize_folder", "send_whatsapp", "send_email", "run_routine", "take_screenshot", "describe_screen", "open_settings_page", "create_folder"}

def _wrap(fn):
    import functools
    @functools.wraps(fn)
    def inner(*a, **k):
        from . import bus
        if bus.locked and fn.__name__ in CONTROL:
            return "PC control is LOCKED by the user (HUD switch). Tell him to switch it to ARMED."
        arg = ", ".join([repr(x)[:40] for x in a] + [f"{kk}={repr(v)[:40]}" for kk, v in k.items()])
        bus.log("tool", f"{fn.__name__}({arg})")
        try: extras.record_call(fn.__name__, k)
        except Exception: pass
        try:
            res = fn(*a, **k)
        except Exception as e:
            res = f"ERROR: {type(e).__name__}: {e}"
            extras._log_err(f"{fn.__module__.split('.')[-1]}.py {fn.__name__}: {e}")
        try:
            with open(AUDIT, "a", encoding="utf-8") as f: f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {fn.__name__}({arg}) -> {str(res)[:120]}\n")
        except Exception: pass
        return res
    return inner

_seen = set(); TOOLS = []
for _f in _RAW:
    if _f.__name__ not in _seen: _seen.add(_f.__name__); TOOLS.append(_wrap(_f))

try: extras.load_plugins()
except Exception: pass
