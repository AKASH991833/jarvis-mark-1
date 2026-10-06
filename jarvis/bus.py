"""Tiny hooks so the window (or console) can show what is happening."""
def _log(role, text):
    col = {"jarvis": "\033[96mJarvis:\033[0m", "user": "\033[92mYou:\033[0m", "tool": "\033[93m>>\033[0m"}.get(role, "[info]")
    print(col, text)
log = _log
state = lambda s: None      # idle | listening | thinking | speaking
level = lambda v: None      # mic loudness 0..1 (for the visualizer)
mic_muted = False           # set by the HUD mic button
locked = False              # set by the HUD ARMED/LOCKED switch (kill switch for PC control)
info = {"voice": "-", "model": "-", "stt": "-"}   # shown in HUD readouts
