"""Tiny hooks so the window (or console) can show what is happening."""
def _log(role, text):
    col = {"jarvis": "\033[96mJarvis:\033[0m", "user": "\033[92mYou:\033[0m", "tool": "\033[93m>>\033[0m"}.get(role, "[info]")
    print(col, text)
log = _log
state = lambda s: None      # idle | listening | thinking | speaking
level = lambda v: None      # mic loudness 0..1 (for the visualizer)
# shared flags (the HUD replaces log/state/level with its own). Defaults make console mode work.
locked = False              # PC control kill switch (HUD button)
mic_muted = False           # mic mute (HUD button)
info = {}                   # small status strings for the HUD (brain, voice, ...)
