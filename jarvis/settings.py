"""Small saved settings (data/settings.json): which brain to use, which local model."""
import json
from . import config

F = config.DATA_DIR / "settings.json"
DEFAULTS = {"backend": "auto", "ollama_model": "", "ollama_url": "http://localhost:11434"}

def load():
    d = dict(DEFAULTS)
    try:
        d.update(json.loads(F.read_text("utf-8")))
    except Exception:
        pass
    return d

def save(**kw):
    d = load(); d.update(kw)
    F.write_text(json.dumps(d, indent=1), "utf-8")
    return d
