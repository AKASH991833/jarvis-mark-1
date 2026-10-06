"""J.A.R.V.I.S HUD (arc-reactor style): glowing blue ring, gauges, weather/news/system widgets, comms log."""
import tkinter as tk, math, queue, time, datetime, os, threading, json, urllib.request, urllib.parse, re, webbrowser
from . import bus, config

BG = "#01050b"
BGRGB = (1, 5, 11)
BLUE = (22, 150, 255)
CYAN = (70, 225, 255)
WHITE = (225, 245, 255)
STATE = {"idle": (40, 200, 255), "listening": (60, 255, 170), "thinking": (255, 180, 50), "speaking": (190, 130, 255)}
LABEL = {"idle": "STANDBY", "listening": "LISTENING", "thinking": "PROCESSING", "speaking": "SPEAKING"}
FONT = "Consolas"
NODES = ["UP", "COMP", "DOCS", "CTRL", "SYS", "WEB", "MAIL", "VOICE", "NET", "FILES", "GUI", "INST", "AI", "MEM", "NEWS", "WX", "SEC", "LOG", "CMD", "SYNC"]
LINKS = [("YOUTUBE", "https://www.youtube.com"), ("GOOGLE", "https://www.google.com"), ("GMAIL", "https://mail.google.com"),
         ("DRIVE", "https://drive.google.com"), ("GITHUB", "https://github.com"), ("WHATSAPP", "https://web.whatsapp.com"), ("AI STUDIO", "https://aistudio.google.com")]

def hexc(rgb, k=1.0):
    k = max(0.0, min(1.0, k))
    return "#%02x%02x%02x" % tuple(int(BGRGB[i] + (rgb[i] - BGRGB[i]) * k) for i in range(3))

class App:
    def __init__(self, n_tools=0):
        self.q = queue.Queue(); self.typed = queue.Queue(); self.st = "idle"
        self.t0 = time.time(); self.level = 0.0; self.target = 0.0
        self.caption = ""; self.cap_t = 0.0; self.on_ready = None; self.ready_fired = False
        self.n_tools = n_tools; self.bars = [0.0] * 64; self.sys = {}; self.sys_t = 0.0
        self.weather = None; self.news = []; self.net = {"ip": "-", "ok": None}; self.notes = []
        r = self.root = tk.Tk(); r.title("J.A.R.V.I.S"); r.geometry("1280x760"); r.minsize(1000, 640); r.configure(bg=BG)
        self.cv = tk.Canvas(r, bg=BG, highlightthickness=0); self.cv.pack(fill="both", expand=True)
        self.txt = tk.Text(r, bg="#020b16", fg="#bfe9ff", font=(FONT, 9), wrap="word", bd=0, padx=6, pady=4, state="disabled",
                           highlightthickness=1, highlightbackground="#0b3d66", cursor="arrow")
        for tag, c in (("jarvis", "#5fe0ff"), ("user", "#6dffb0"), ("info", "#6b7f93"), ("tool", "#ffc25a")):
            self.txt.tag_config(tag, foreground=c)
        self.ent = tk.Entry(r, bg="#020b16", fg="#e6f7ff", insertbackground="#5fe0ff", font=(FONT, 12), bd=0, justify="center",
                            highlightthickness=1, highlightbackground="#0b3d66", highlightcolor="#19a6ff")
        self.ent.bind("<Return>", self._send); self.ent.focus()
        self.w_txt = self.cv.create_window(0, 0, window=self.txt, anchor="nw")
        self.w_ent = self.cv.create_window(0, 0, window=self.ent, anchor="nw")
        self.buttons = []
        self.fx = {"particles", "wave", "slide", "progress", "edge"}
        self.task = None; self.task_t = 0.0; self.banner = ""; self.ready_t = None; self.force_slide = None
        import random; self.rnd = random
        self.parts = [[random.random() * 6.28, random.random(), random.uniform(.4, 1.0)] for _ in range(130)]
        self.cv.bind("<Button-1>", self._click)
        bus.log = lambda role, text: self.q.put(("log", role, text))
        bus.state = lambda s: self.q.put(("state", s, ""))
        bus.level = lambda v: setattr(self, "target", v)
        self.boot_lines = ["J.A.R.V.I.S MARK-1 KERNEL ........... OK", "NEURAL LINK (GEMINI) ............. ONLINE",
                           "LOCAL BRAIN (OLLAMA) ............. STANDBY", "VOICE SYNTHESIS (ACHIRD) ......... READY",
                           "SPEECH RECOGNITION ............... ARMED", f"PC CONTROL MODULES ................ {n_tools} LOADED",
                           "SAFETY LOCKS ..................... ACTIVE", "ALL SYSTEMS NOMINAL. WELCOME BACK."]
        threading.Thread(target=self._bg_fetch, daemon=True).start()
        r.after(33, self._frame)

    # ------------------------------------------------------------ background data (weather / news / network)
    def _bg_fetch(self):
        last_w = last_n = 0
        while True:
            now = time.time()
            if now - last_w > 600:
                last_w = now
                try:
                    u = "https://wttr.in/" + urllib.parse.quote(config.WEATHER_CITY) + "?format=j1"
                    d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "curl/8"}), timeout=15).read().decode())
                    c = d["current_condition"][0]
                    self.weather = {"city": config.WEATHER_CITY.upper(), "t": c["temp_C"], "feel": c["FeelsLikeC"], "desc": c["weatherDesc"][0]["value"],
                                    "hum": c["humidity"], "wind": c["windspeedKmph"],
                                    "days": [(w["date"][5:], w["maxtempC"], w["mintempC"], w["hourly"][4]["weatherDesc"][0]["value"]) for w in d["weather"][:3]]}
                except Exception: pass
            if now - last_n > 900:
                last_n = now
                try:
                    x = urllib.request.urlopen(urllib.request.Request("https://news.google.com/rss/search?q=India&hl=en-IN&gl=IN&ceid=IN:en", headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read().decode("utf-8", "ignore")
                    self.news = [re.sub(r" - [^-]+$", "", h) for h in re.findall(r"<item>.*?<title>(.*?)</title>", x, re.S)[:5]]
                except Exception: pass
            try:
                import socket
                self.net["ip"] = socket.gethostbyname(socket.gethostname())
                urllib.request.urlopen("https://www.google.com", timeout=5); self.net["ok"] = True
            except Exception: self.net["ok"] = False
            try:
                nf = config.DATA_DIR / "notes.txt"
                self.notes = nf.read_text("utf-8").splitlines()[-4:] if nf.exists() else []
            except Exception: pass
            time.sleep(30)

    # ------------------------------------------------------------ input
    def _send(self, _=None):
        t = self.ent.get().strip()
        if t:
            self.ent.delete(0, "end"); self.typed.put(t); self.q.put(("log", "user", t))

    def _click(self, e):
        for x0, y0, x1, y1, act in self.buttons:
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                act(); return

    def _quick(self, text): self.typed.put(text); self.q.put(("log", "user", text))
    def _toggle_mic(self): bus.mic_muted = not bus.mic_muted
    def _toggle_lock(self):
        bus.locked = not bus.locked
        self.q.put(("log", "info", "PC CONTROL LOCKED - Jarvis cannot touch the PC" if bus.locked else "PC CONTROL ARMED"))

    # ------------------------------------------------------------ drawing helpers
    def _arc(self, cx, cy, r, start, ext, c, w=2, glow=True):
        cv = self.cv
        if glow:
            cv.create_arc(cx - r, cy - r, cx + r, cy + r, start=start, extent=ext, style="arc", outline=hexc(c, .14), width=w + 7)
            cv.create_arc(cx - r, cy - r, cx + r, cy + r, start=start, extent=ext, style="arc", outline=hexc(c, .4), width=w + 3)
        cv.create_arc(cx - r, cy - r, cx + r, cy + r, start=start, extent=ext, style="arc", outline=hexc(c, 1), width=w)

    def _circ(self, cx, cy, r, c, k=1.0, w=1, fill="", dash=None):
        kw = {"dash": dash} if dash else {}
        self.cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=hexc(c, k), width=w, fill=fill, **kw)

    def _text(self, x, y, s, c, size=10, anchor="nw", bold=False, **kw):
        self.cv.create_text(x, y, text=s, fill=c, anchor=anchor, font=(FONT, size, "bold" if bold else "normal"), **kw)

    def _bracket(self, x0, y0, x1, y1, c, L=14):
        for (x, y, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            self.cv.create_line(x, y + dy * L, x, y, x + dx * L, y, fill=c, width=2)

    def _refresh_sys(self):
        try:
            import psutil, shutil
            b = psutil.sensors_battery(); d = shutil.disk_usage(os.path.abspath(os.sep))
            dl = os.path.join(os.path.expanduser("~"), "Downloads")
            try: nd = len(os.listdir(dl))
            except Exception: nd = 0
            self.sys = {"cpu": psutil.cpu_percent(None), "ram": psutil.virtual_memory().percent, "disk": d.used / d.total * 100,
                        "free": d.free / 2**30, "bat": (b.percent, b.power_plugged) if b else None,
                        "up": datetime.timedelta(seconds=int(time.time() - psutil.boot_time())), "procs": len(psutil.pids()), "dl": nd}
        except Exception: pass

    # ------------------------------------------------------------ frame loop
    def _frame(self):
        try: self._drain(); self._draw()
        except Exception as e: print("[ui]", e)
        self.root.after(40, self._frame)

    def _drain(self):
        try:
            while True:
                k, a, b = self.q.get_nowait()
                if k == "state": self.st = a
                else:
                    who = {"jarvis": "JARVIS", "user": config.USER_NAME.upper(), "tool": "EXEC", "info": "SYS"}.get(a, "SYS")
                    self.txt.config(state="normal")
                    self.txt.insert("end", f"[{time.strftime('%H:%M')}] {who} > {b}\n", a)
                    self.txt.see("end"); self.txt.config(state="disabled")
                    if a == "jarvis": self.caption, self.cap_t = b, time.time()
                    if a == "tool": self.task = {"name": b.split("(")[0].replace("_", " ").upper(), "pct": 3.0}; self.task_t = time.time()
        except queue.Empty: pass

    def _draw(self):
        cv = self.cv; W, H = cv.winfo_width(), cv.winfo_height()
        if W < 100: return
        for item in cv.find_all():
            if item not in (self.w_txt, self.w_ent): cv.delete(item)
        t = time.time() - self.t0
        self.buttons = []
        # faint grid
        gc = hexc(BLUE, .06)
        for x in range(0, W, 40): cv.create_line(x, 0, x, H, fill=gc)
        for y in range(0, H, 40): cv.create_line(0, y, W, y, fill=gc)
        if t < 5.0: return self._boot(W, H, t)
        if not self.ready_fired:
            self.ready_fired = True; self.ready_t = time.time()
            cv.itemconfigure(self.w_txt, state="normal"); cv.itemconfigure(self.w_ent, state="normal"); self.ent.focus()
            if self.on_ready: self.on_ready()
        if time.time() - self.sys_t > 1.5: self.sys_t = time.time(); self._refresh_sys()
        sc = self.sys; S = bus.info
        c = STATE[self.st]
        cx = W // 2; top = 74; bot = H - 165
        cy = (top + bot) // 2
        R = max(70, min((bot - top) / 2 / 1.62, (W - 640) / 2 / 1.62))
        self._hud_ring(cx, cy, R, t, c, sc)
        self._fx_layers(W, H, cx, cy, R, t, c)
        now = datetime.datetime.now()
        self._text(cx, cy - 2, now.strftime("%H:%M"), "#e6f7ff", max(10, int(R / 7)), "center", True)
        self._text(cx, cy + R * .12, now.strftime("%S"), hexc(c, 1), max(8, int(R / 11)), "center")
        self._topbar(W, t, sc)
        dxl, dxr = self._slide_offsets(W, t)
        self._left(W, H, top, H - 125, sc, dxl)
        self._right(W, H, top, H - 125, dxr)
        if self.banner: self._banner(W)
        self._bottom(W, H, cx, cy, R, c, sc)

    def _boot(self, W, H, t):
        cv = self.cv; cx, cy = W // 2, H // 2
        cv.itemconfigure(self.w_txt, state="hidden"); cv.itemconfigure(self.w_ent, state="hidden")
        # hex-ish dot field that lights up behind the scan line
        sy = (t / 4.6) * H
        for gy in range(0, H, 28):
            for gx in range((gy // 28 % 2) * 14, W, 28):
                if gy < sy: cv.create_oval(gx, gy, gx + 2, gy + 2, outline="", fill=hexc(BLUE, .35 + .2 * math.sin(gx * .05 + t * 3)))
        # scan beam
        for k, a in ((26, .05), (14, .1), (6, .22), (2, .9)): cv.create_rectangle(0, sy - k // 2, W, sy + k // 2, outline="", fill=hexc(CYAN, a))
        # ring assembling from arcs
        frac = min(1.0, t / 4.2); R = 95
        cyr = cy - 150
        for i, (rr, w) in enumerate(((R, 6), (R * .78, 3), (R * 1.25, 2), (R * 1.5, 1))):
            ext = 359 * min(1, max(0, frac * 1.6 - i * .15))
            self._arc(cx, cyr, rr, (t * (90 - i * 40)) % 360, ext, BLUE if i % 2 else CYAN, w)
        self._text(cx, cyr, "J", "#46e1ff", 30, "center", True)
        n = int(min(len(self.boot_lines), t / 0.5))
        for i in range(n):
            ln = self.boot_lines[i]; done = i < n - 1 or t > 4.4
            left, _, right = ln.partition(" ...")
            y = cy + 10 + i * 22
            self._text(cx - 260, y, left.strip(), hexc(WHITE, .9 if done else .6), 10)
            self._text(cx + 260, y, "[ OK ]" if done else "[ ... ]", "#3dffa0" if done else "#ffc25a", 10, "ne", True)
        cv.create_rectangle(cx - 260, cy + 212, cx + 260, cy + 224, outline=hexc(BLUE, .8))
        cv.create_rectangle(cx - 258, cy + 214, cx - 258 + 516 * frac, cy + 222, outline="", fill=hexc(CYAN, 1))
        self._text(cx, cy + 238, f"SYSTEM CHECK {int(frac * 100)}%", "#78b8da", 9, "n")
        for yy in range(0, H, 4): cv.create_line(0, yy, W, yy, fill=hexc(BLUE, .035))

    # ------------------------------------------------------------ the reactor
    def _hud_ring(self, cx, cy, R, t, c, sc):
        cv = self.cv
        # outer thin rings with gaps
        self._circ(cx, cy, R * 1.62, BLUE, .25)
        for i in range(4): self._arc(cx, cy, R * 1.58, t * 12 + i * 90, 55, BLUE, 2)
        self._circ(cx, cy, R * 1.46, BLUE, .35, 1, dash=(2, 6))
        # 4 gauge nodes (CPU, RAM, DISK, POWER)
        gauges = [("CPU", sc.get("cpu", 0)), ("RAM", sc.get("ram", 0)), ("HDD", sc.get("disk", 0)), ("PWR", (sc["bat"][0] if sc.get("bat") else 100))]
        for k, (lab, val) in enumerate(gauges):
            a = math.radians(45 + 90 * k + 0)
            gx, gy = cx + R * 1.58 * math.cos(a), cy - R * 1.58 * math.sin(a)
            self._circ(gx, gy, 20, BLUE, .3, 1, fill="#020b16")
            self._arc(gx, gy, 20, 90, -3.6 * val, CYAN, 3)
            self._text(gx, gy - 4, f"{val:.0f}", "#e6f7ff", 9, "center", True)
            self._text(gx, gy + 8, lab, "#4d9ac7", 7, "center")
        # button ring (annulus sectors with labels)
        n = len(NODES); step = 360 / n
        hot = int(t * 2) % n if self.st in ("thinking",) else (int(t * 0.8) % n)
        r0, r1 = R * 1.13, R * 1.36
        for i, name in enumerate(NODES):
            a0 = math.radians(i * step + 2 + t * 1.5); a1 = math.radians((i + 1) * step - 2 + t * 1.5)
            pts = []
            for a in (a0, a1): pts += [cx + r1 * math.cos(a), cy - r1 * math.sin(a)]
            for a in (a1, a0): pts += [cx + r0 * math.cos(a), cy - r0 * math.sin(a)]
            act = (i == hot)
            cv.create_polygon(*pts, outline=hexc(CYAN if act else BLUE, .95 if act else .55), fill=hexc(BLUE, .35 if act else .08), width=1)
            am = (a0 + a1) / 2; rm = (r0 + r1) / 2
            ang = (math.degrees(am) - 90) % 360
            ang = ang + 180 if 90 < ang < 270 else ang
            cv.create_text(cx + rm * math.cos(am), cy - rm * math.sin(am), text=name, fill=hexc(WHITE, .9 if act else .55), font=(FONT, 7), angle=-math.degrees(am) + 90 + (180 if math.sin(am) < 0 else 0))
        # main glowing ring
        for w, k in ((46, .06), (36, .10), (26, .18), (18, .32)):
            self._circ(cx, cy, R * 1.0, BLUE, k, w)
        self._circ(cx, cy, R * 1.0, CYAN, .95, 8)
        self._circ(cx, cy, R * 1.0, WHITE, .9, 3)
        self._circ(cx, cy, R * 1.1, CYAN, .8, 2)
        self._circ(cx, cy, R * 0.9, CYAN, .8, 2)
        # striped band inside the ring
        for i in range(60):
            st = i * 6 + t * 7
            col = WHITE if i % 2 == 0 else (30, 90, 170)
            cv.create_arc(cx - R * .8, cy - R * .8, cx + R * .8, cy + R * .8, start=st, extent=3.2, style="arc", outline=hexc(col, 1 if i % 2 == 0 else .8), width=9)
        self._circ(cx, cy, R * .72, CYAN, .9, 2)
        self._circ(cx, cy, R * .71, BGRGB, 1, 0, fill=BG)
        # ticks inside
        for i in range(72):
            a = math.radians(i * 5 - t * 6); L = 7 if i % 6 == 0 else 3
            r1 = R * .68; r2 = r1 - L
            cv.create_line(cx + r1 * math.cos(a), cy + r1 * math.sin(a), cx + r2 * math.cos(a), cy + r2 * math.sin(a), fill=hexc(BLUE, .7 if i % 6 == 0 else .35))
        # voice visualizer (state coloured)
        n = len(self.bars)
        if self.st == "listening": self.level += (self.target - self.level) * .5
        elif self.st == "speaking": self.level += ((.35 + .5 * abs(math.sin(t * 9) * math.sin(t * 3.1))) - self.level) * .35
        elif self.st == "thinking": self.level += (.2 + .1 * math.sin(t * 12) - self.level) * .2
        else: self.level += (.06 - self.level) * .15
        for i in range(n):
            a = 2 * math.pi * i / n
            tg = self.level * (.5 + .9 * abs(math.sin(i * .7 + t * 6) * math.cos(i * .31 - t * 3))) + .03
            self.bars[i] += (tg - self.bars[i]) * .4
            b0 = R * .36; b1 = b0 + 4 + self.bars[i] * R * .42
            cv.create_line(cx + b0 * math.cos(a), cy + b0 * math.sin(a), cx + b1 * math.cos(a), cy + b1 * math.sin(a), fill=hexc(c, .5 + self.bars[i]), width=3)
        # core
        for a in (t * 40, -t * 55):
            self._arc(cx, cy, R * .3, a, 100, c, 2)
        self._circ(cx, cy, R * .22, c, .9, 2, fill="#02101f")
        self._core_clock = (cx, cy, R, c)


    # ------------------------------------------------------------ extra effects
    def _slide_offsets(self, W, t):
        if "slide" not in self.fx: return 0, 0
        if self.force_slide is not None: return -self.force_slide, self.force_slide
        if self.ready_t is None: return 0, 0
        k = max(0.0, min(1.0, (time.time() - self.ready_t) / 0.9)); e = 1 - (1 - k) ** 3
        off = (1 - e) * 320
        return -off, off

    def _fx_layers(self, W, H, cx, cy, R, t, c):
        cv = self.cv
        if self.force_slide:
            for side in (1, -1):
                bx = (W - 280 + self.force_slide) if side == 1 else (260 - self.force_slide)
                for i in range(10):
                    y = 90 + i * 45; L = 40 + (i * 37) % 90
                    cv.create_line(bx, y, bx + side * L, y, fill=hexc(CYAN, .5 - i * .03), width=2)
                    cv.create_line(bx, y + 6, bx + side * L * .6, y + 6, fill=hexc(BLUE, .4), width=1)
        if "edge" in self.fx:
            s = {"listening": 1.0, "speaking": .55, "thinking": .4, "idle": .12}[self.st] * (0.8 + 0.2 * math.sin(t * 4))
            for i in range(16):
                k = ((1 - i / 16) ** 2.2) * s
                cv.create_rectangle(i * 3, i * 3, W - i * 3, H - i * 3, outline=hexc(c, k), width=3)
        if "particles" in self.fx:
            sp = {"idle": .4, "listening": .9, "speaking": 1.4, "thinking": 3.2}[self.st]
            for p in self.parts:
                p[0] += .012 * sp * p[2] * (1 + (1 - p[1]) * 1.5)
                rr = R * (.1 + p[1] * .52); a = p[0]
                x, y = cx + rr * math.cos(a), cy + rr * math.sin(a)
                for tr in (3, 2, 1):
                    a2 = a - .05 * tr * sp
                    cv.create_oval(cx + rr * math.cos(a2) - 1, cy + rr * math.sin(a2) - 1, cx + rr * math.cos(a2) + 1, cy + rr * math.sin(a2) + 1, outline="", fill=hexc(CYAN, .3 * (4 - tr) * p[2]))
                cv.create_oval(x - 3, y - 3, x + 3, y + 3, outline="", fill=hexc(CYAN, .35 * p[2]))
                cv.create_oval(x - 1.5, y - 1.5, x + 1.5, y + 1.5, outline="", fill=hexc(WHITE, p[2]))
        if "wave" in self.fx:
            pts = []
            for i in range(0, 361, 3):
                a = math.radians(i)
                amp = (self.level * .9 + .04) * R * .16
                r = R * 1.47 + amp * (math.sin(a * 9 + t * 7) * .6 + math.sin(a * 17 - t * 5) * .4)
                pts += [cx + r * math.cos(a), cy - r * math.sin(a)]
            cv.create_line(*pts, fill=hexc(c, .15), width=8, smooth=True)
            cv.create_line(*pts, fill=hexc(c, .45), width=4, smooth=True)
            cv.create_line(*pts, fill=hexc(WHITE, .95), width=1, smooth=True)
        if "progress" in self.fx:
            tk_ = self.task
            if tk_ and time.time() - self.task_t > 0:
                age = time.time() - self.task_t
                if self.st == "idle" and age > 1.5 and tk_["pct"] < 100: tk_["pct"] = 100; self.task_t = time.time() - 1.0
                elif tk_["pct"] < 92: tk_["pct"] += (92 - tk_["pct"]) * .015
                if tk_["pct"] >= 100 and age > 3.0: self.task = None
                else:
                    r = R * 1.2
                    cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=hexc(BLUE, .25), width=3)
                    self._arc(cx, cy, r, 90, -3.6 * tk_["pct"], CYAN if tk_["pct"] < 100 else (60, 255, 160), 5)
                    self._text(cx, cy + R * .52, f"{tk_['name'][:22]}", "#bfe9ff", 8, "center")
                    self._text(cx, cy + R * .62, f"{tk_['pct']:.0f}%", "#46e1ff", 10, "center", True)

    def _banner(self, W):
        self.cv.create_rectangle(W // 2 - 230, 70, W // 2 + 230, 98, outline=hexc(CYAN, .9), fill="#02101f")
        self._text(W // 2, 84, self.banner, "#e6f7ff", 11, "center", True)

    # ------------------------------------------------------------ widgets
    def _bar(self, x, y, w, frac, c, label, val):
        self._text(x, y, label, "#5b9cc4", 8); self._text(x + w, y, val, "#d8f4ff", 8, "ne")
        self.cv.create_rectangle(x, y + 13, x + w, y + 18, outline=hexc(c, .5), fill="#020b16")
        self.cv.create_rectangle(x + 1, y + 14, x + 1 + max(0, min(1, frac)) * (w - 2), y + 17, outline="", fill=hexc(c, 1))

    def _topbar(self, W, t, sc):
        cv = self.cv; now = datetime.datetime.now()
        cv.create_line(0, 62, W, 62, fill=hexc(BLUE, .35))
        self._text(18, 10, "J.A.R.V.I.S", "#46e1ff", 17, "nw", True)
        self._text(18, 38, "MARK-1  //  PERSONAL INTELLIGENCE SYSTEM", "#4d86a8", 8)
        if sc:
            x = 290
            for lab, v in (("CPU", sc["cpu"]), ("RAM", sc["ram"]), ("HDD", sc["disk"])):
                self._bar(x, 12, 70, v / 100, BLUE, lab, f"{v:.0f}%"); x += 90
        self._text(W // 2, 8, now.strftime("%A, %d %B %Y").upper(), "#78b8da", 10, "n")
        self._text(W // 2, 24, now.strftime("%I:%M:%S %p"), "#e6f7ff", 16, "n", True)
        ok = self.net["ok"]
        self._text(W - 18, 10, "ONLINE" if ok else ("OFFLINE" if ok is False else "..."), "#3dffa0" if ok else "#ff6b6b", 10, "ne", True)
        self._text(W - 18, 28, f"IP {self.net['ip']}", "#4d86a8", 8, "ne")
        self._text(W - 18, 42, "VOICE " + bus.info.get("voice", "-"), "#4d86a8", 8, "ne")

    def _left(self, W, H, top, bot, sc, dx=0):
        x = 24 + dx; y = top + 8; w = 230
        self._bracket(10 + dx, top, x + w + 6, bot + 10, hexc(BLUE, .55))
        self._text(x, y, "MODULES", "#46e1ff", 10, "nw", True); y += 22
        for k, v in (("BRAIN", bus.info.get("brain", "-")), ("VOICE", bus.info.get("voice", "-")),
                     ("EARS", "GROQ WHISPER" if config.GROQ_API_KEY else "GEMINI AUDIO"), ("MIC", "MUTED" if bus.mic_muted else "LIVE"),
                     ("CONTROL", "LOCKED" if bus.locked else "ARMED")):
            self._text(x, y, k, "#5b9cc4", 8); self._text(x + w, y, str(v)[:18], "#ff6b6b" if v in ("MUTED", "LOCKED") else "#d8f4ff", 8, "ne"); y += 16
        y += 12
        self._text(x, y, "TO DO LIST", "#46e1ff", 10, "nw", True); y += 20
        for n in (self.notes or ["(say: note likho ...)"]):
            self._text(x, y, "- " + re.sub(r"^\[[^\]]*\]\s*", "", n)[:30], "#8fc3de", 8); y += 15
        y += 12
        self._text(x, y, "LINKS", "#46e1ff", 10, "nw", True); y += 20
        for name, url in LINKS:
            if y > bot - 8: break
            self._text(x + 8, y, name, "#8fd8ff", 9, "nw")
            self.buttons.append((x, y - 2, x + 150, y + 14, (lambda u=url: webbrowser.open(u)))); y += 18

    def _right(self, W, H, top, bot, dx=0):
        x = W - 262 + dx; w = 240; y = top + 8
        self._bracket(x - 14, top, W - 10 + dx, bot + 10, hexc(BLUE, .55))
        wx = self.weather
        if wx:
            self._text(x, y, wx["city"], "#5b9cc4", 8); y += 14
            self._text(x, y, f"{wx['t']}\u00b0C", "#e6f7ff", 26, "nw", True)
            self._text(x + w, y + 2, wx["desc"].upper()[:16], "#8fd8ff", 9, "ne"); self._text(x + w, y + 18, f"feels {wx['feel']}\u00b0  hum {wx['hum']}%", "#5b9cc4", 8, "ne"); self._text(x + w, y + 31, f"wind {wx['wind']} km/h", "#5b9cc4", 8, "ne"); y += 48
            for d, hi, lo, ds in wx["days"][:3]:
                self._text(x, y, d, "#5b9cc4", 8); self._text(x + 50, y, f"{hi}\u00b0/{lo}\u00b0", "#d8f4ff", 8); self._text(x + w, y, ds[:20], "#8fc3de", 8, "ne"); y += 15
        else:
            self._text(x, y, "WEATHER ...", "#5b9cc4", 9); y += 40
        y += 10
        self._text(x, y, "HEADLINES", "#46e1ff", 10, "nw", True); y += 20
        for h in (self.news or ["loading..."])[:4]:
            self.cv.create_text(x, y, text="> " + h[:58], fill="#8fc3de", font=(FONT, 8), anchor="nw", width=w); y += 36
        ly = max(y + 6, int(H * 0.5)); lh = bot - ly + 4
        self._text(x, ly - 16, "COMMS LOG", "#46e1ff", 9, "nw", True)
        self.cv.coords(self.w_txt, x - 4, ly); self.cv.itemconfigure(self.w_txt, width=w + 8, height=max(60, lh))

    def _bottom(self, W, H, cx, cy, R, c, sc):
        cv = self.cv
        cv.create_line(0, H - 112, W, H - 112, fill=hexc(BLUE, .3))
        self._text(cx, cy + R * 1.62 + 8, LABEL[self.st], hexc(c, 1), 12, "n", True)
        if self.caption and time.time() - self.cap_t < 14:
            cap = self.caption if len(self.caption) < 120 else self.caption[:117] + "..."
            cv.create_text(cx, cy + R * 1.62 + 30, text=cap, fill="#a6d9f0", font=(FONT, 10), width=560, anchor="n", justify="center")
        if sc:
            x = 24; y = H - 100
            self._text(x, y, f"DOWNLOADS :: {sc['dl']} items", "#6fa8c4", 8); self._text(x, y + 14, f"FREE DISK :: {sc['free']:.0f} GB", "#6fa8c4", 8)
            self._text(x, y + 28, f"UPTIME :: {str(sc['up']).split('.')[0]}   PROCS :: {sc['procs']}", "#6fa8c4", 8)
            if sc["bat"]: self._text(x, y + 42, f"POWER :: {sc['bat'][0]:.0f}% {'(AC)' if sc['bat'][1] else '(BATTERY)'}", "#6fa8c4", 8)
        # buttons
        bx = [cx - 360]
        def btn(label, act, hot=False, col=BLUE):
            ww = len(label) * 7 + 22; x = bx[0]; y = H - 108 + 8
            cv.create_rectangle(x, y, x + ww, y + 24, outline=hexc((255, 90, 90) if hot else col, .9), fill=hexc((255, 90, 90) if hot else col, .12))
            self._text(x + ww / 2, y + 12, label, "#ff9a9a" if hot else "#8fd8ff", 8, "center", True)
            self.buttons.append((x, y, x + ww, y + 24, act)); bx[0] += ww + 8
        btn("MIC " + ("MUTED" if bus.mic_muted else "LIVE"), self._toggle_mic, bus.mic_muted)
        btn("PC " + ("LOCKED" if bus.locked else "ARMED"), self._toggle_lock, bus.locked)
        for lab, cmd in (("SCREENSHOT", "screenshot lo"), ("SYSTEM", "mere PC ka system status batao"), ("NEWS", "aaj ki top khabrein batao"),
                         ("RESEARCH", "naye free tools aur upgrades research karo"), ("ROUTINE", "morning routine chalao")):
            btn(lab, (lambda c_=cmd: self._quick(c_)))
        cv.coords(self.w_ent, cx - 300, H - 66); cv.itemconfigure(self.w_ent, width=600, height=34)

    def run(self): self.root.mainloop()
