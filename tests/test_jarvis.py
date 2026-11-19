"""Offline tests for JARVIS core logic. No microphone, screen, Windows or internet needed.
Run: python -m unittest discover -s tests -v   (or double-click run_tests.bat)"""
import os, sys, json, time, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import jarvis.config as config
config.DATA_DIR = Path(tempfile.mkdtemp(prefix="jarvis-test-"))
config.MEMORY_FILE = config.DATA_DIR / "memory.json"

import jarvis.bus as bus
import jarvis.pc as pc
import jarvis.extras as extras
import jarvis.remote as remote
import jarvis.agent as agent
import main as main_mod


class TestBusDefaults(unittest.TestCase):
    def test_console_mode_defaults_exist(self):
        # without the HUD, these must exist so console/text mode does not crash
        self.assertIs(bus.locked, False)
        self.assertIs(bus.mic_muted, False)
        self.assertIsInstance(bus.info, dict)
        bus.state("listening"); bus.level(0.5); bus.log("info", "test")   # must not raise


class TestPaths(unittest.TestCase):
    def test_friendly_folder(self):
        p = pc._p("Desktop")
        self.assertTrue(p.endswith("Desktop") or "OneDrive" in p)
    def test_tilde_expands(self):
        p = pc._p("~")
        self.assertEqual(p, os.path.expanduser("~"))


class TestYesNo(unittest.TestCase):
    def test_yes_words(self):
        for w in ("haan", "yes", "kar do", "theek hai", "bilkul", "ok"):
            self.assertTrue(main_mod.has(main_mod.YES, w), w)
    def test_no_words(self):
        for w in ("nahi", "no", "mat karo", "ruk jao", "cancel"):
            self.assertTrue(main_mod.has(main_mod.NO, w), w)
    def test_no_false_positive(self):
        self.assertFalse(main_mod.has(main_mod.YES, "nahi karna"))


class TestReminders(unittest.TestCase):
    def setUp(self):
        pc.REMINDERS = config.DATA_DIR / "reminders.json"
        if pc.REMINDERS.exists(): pc.REMINDERS.unlink()
    def test_set_list_cancel(self):
        r = pc.set_reminder(30, "paani peena")
        self.assertIn("30", r)
        lst = pc.list_reminders()
        self.assertIn("paani peena", lst)
        c = pc.cancel_reminder("paani")
        self.assertIn("cancel", c)
        self.assertEqual(pc.list_reminders(), "Koi reminder pending nahi hai.")
    def test_persistence_roundtrip(self):
        pc.set_reminder(60, "restart test")
        rs = pc._load_reminders()
        self.assertEqual(len(rs), 1)
        self.assertEqual(rs[0]["message"], "restart test")
        pc.cancel_reminder("restart test")


class TestRoutines(unittest.TestCase):
    def test_save_and_default(self):
        pc.ROUTINES = config.DATA_DIR / "routines.json"
        if pc.ROUTINES.exists(): pc.ROUTINES.unlink()
        r = pc.save_routine("coding", "code, youtube.com")
        self.assertIn("coding", r)
        d = json.loads(pc.ROUTINES.read_text())
        self.assertEqual(d["coding"], ["code", "youtube.com"])
        opened = []
        pc.open_app, pc.open_website = lambda x: opened.append(x) or "ok", lambda x: opened.append(x) or "ok"
        out = pc.run_routine("coding")
        self.assertIn("coding", out)
        self.assertEqual(opened, ["code", "youtube.com"])
        self.assertIn("No such routine", pc.run_routine("nope"))


class TestClipboardHistory(unittest.TestCase):
    def test_empty_then_list(self):
        pc.CLIP_HIST = config.DATA_DIR / "clip.json"
        if pc.CLIP_HIST.exists(): pc.CLIP_HIST.unlink()
        self.assertIn("Abhi", pc.clipboard_history("list"))
        pc.CLIP_HIST.write_text(json.dumps([{"t": "10:00", "text": "hello world"}]))
        self.assertIn("hello world", pc.clipboard_history("list"))


class TestVoiceGate(unittest.TestCase):
    def setUp(self):
        remote.PRINT = config.DATA_DIR / "voiceprint.json"
        if remote.PRINT.exists(): remote.PRINT.unlink()
        remote._gate["until"] = 0.0; remote._gate["warned"] = 0.0
        os.environ.pop("VOICE_GATE", None); os.environ.pop("VOICE_PIN", None)
    def test_off_allows(self):
        ok, msg = remote.gate_check("chrome kholo", b"1234567890")
        self.assertTrue(ok); self.assertIsNone(msg)
    def test_typed_always_allowed(self):
        os.environ["VOICE_GATE"] = "pin"
        ok, msg = remote.gate_check("chrome kholo", None)
        self.assertTrue(ok)
    def test_voiceprint_missing_warns_not_crashes(self):
        os.environ["VOICE_GATE"] = "voiceprint"
        ok, msg = remote.gate_check("chrome kholo", b"1234567890")
        self.assertTrue(ok)                      # gate stays open until a print exists
        self.assertIsNotNone(msg)                # first time warns
        ok2, msg2 = remote.gate_check("chrome kholo", b"1234567890")
        self.assertIsNone(msg2)                  # then stays quiet
    def test_pin_unlock_and_lock(self):
        os.environ["VOICE_GATE"] = "pin"; os.environ["VOICE_PIN"] = "1234"
        ok, msg = remote.gate_check("chrome kholo", b"1234567890")
        self.assertFalse(ok)                     # locked without PIN
        ok, msg = remote.gate_check("jarvis unlock ek do teen char", b"1234567890")
        self.assertFalse(ok)                     # unlock phrase itself is not a command
        self.assertIn("Unlock", msg)
        ok, msg = remote.gate_check("chrome kholo", b"1234567890")
        self.assertTrue(ok)                      # unlocked for VOICE_GATE_MINUTES
    def test_norm_digits(self):
        self.assertEqual(remote._norm_digits("ek do teen char"), "1234")
        self.assertEqual(remote._norm_digits("one two 3 4"), "1234")


class TestBrainSchema(unittest.TestCase):
    def test_schema(self):
        def sample(a: str, n: int = 3) -> str:
            """Do a thing."""
            return a
        from jarvis.brain import _schema
        s = _schema(sample)
        self.assertEqual(s["function"]["name"], "sample")
        self.assertEqual(s["function"]["parameters"]["required"], ["a"])
        self.assertEqual(s["function"]["parameters"]["properties"]["n"]["type"], "integer")


class TestNewTools(unittest.TestCase):
    def test_translate_langs(self):
        # offline: only the mapping logic (no network call)
        src = Path(pc.__file__).read_text()
        self.assertIn('"hindi": "hi"', src)
    def test_focus_mode_flag(self):
        pc._focus["until"] = 0.0
        self.assertFalse(pc.focus_active())
        pc._focus["until"] = time.time() + 60
        self.assertTrue(pc.focus_active())
        pc._focus["until"] = 0.0
    def test_tools_registered(self):
        names = {t.__name__ for t in pc.TOOLS}
        for n in ("snap_window", "clipboard_history", "take_webcam_photo", "currency_convert",
                  "translate_text", "internet_speed_test", "find_large_files", "focus_mode",
                  "list_reminders", "cancel_reminder"):
            self.assertIn(n, names)
    def test_no_duplicate_tools(self):
        names = [t.__name__ for t in pc.TOOLS]
        self.assertEqual(len(names), len(set(names)))
    def test_local_brain_subset_exists(self):
        from jarvis.brain import LOCAL_TOOLS
        names = {t.__name__ for t in pc.TOOLS}
        missing = [n for n in LOCAL_TOOLS if n not in names]
        self.assertEqual(missing, [])


class TestMemory(unittest.TestCase):
    def test_remember_and_load(self):
        config.MEMORY_FILE = config.DATA_DIR / "memory.json"
        if config.MEMORY_FILE.exists(): config.MEMORY_FILE.unlink()
        pc.MEMORY = config.MEMORY_FILE
        self.assertEqual(pc.remember("favourite colour neela hai"), "Remembered.")
        self.assertIn("neela", pc.load_memory())


class TestAgent(unittest.TestCase):
    """v2.1 multi-step control: planner, offline parser, executor, WhatsApp safety."""
    def setUp(self):
        self._dry = agent.DRY_RUN
        self._gen = agent.gen
        self._confirm = pc.confirm
        agent.DRY_RUN = True
        agent.gen = lambda prompt: None          # no brain -> offline parser path
        agent.clear_stop()
        bus.locked = False
    def tearDown(self):
        agent.DRY_RUN = self._dry
        agent.gen = self._gen
        pc.confirm = self._confirm
        agent.clear_stop()

    # ---------------- offline Hinglish parser
    def test_parse_chrome_youtube_single_sentence(self):
        steps = agent.parse_steps_local("chrome kholke youtube pe kesariya chalao")
        self.assertEqual(steps, [{"action": "open_app", "name": "chrome"},
                                 {"action": "play_youtube", "query": "kesariya"}])
    def test_parse_chained_youtube(self):
        steps = agent.parse_steps_local("youtube pe tum hi ho chalao")
        self.assertEqual(steps, [{"action": "play_youtube", "query": "tum hi ho"}])
    def test_parse_two_clauses(self):
        steps = agent.parse_steps_local("chrome kholo aur google pe linux questions search karo")
        self.assertEqual(steps, [{"action": "open_app", "name": "chrome"},
                                 {"action": "search_google", "query": "linux questions"}])
    def test_parse_whatsapp_by_name(self):
        steps = agent.parse_steps_local("whatsapp pe rahul ko message karo happy birthday")
        self.assertEqual(steps, [{"action": "whatsapp", "contact": "rahul", "message": "happy birthday", "send": True}])
    def test_parse_whatsapp_with_enter_press(self):
        steps = agent.parse_steps_local("whatsapp pe mummy ko aaj der se aaunga likh do aur enter daba do")
        self.assertEqual(steps, [{"action": "whatsapp", "contact": "mummy", "message": "aaj der se aaunga", "send": True}])
    def test_parse_whatsapp_dont_send(self):
        steps = agent.parse_steps_local("whatsapp pe rahul ko hello likho mat bhejo")
        self.assertEqual(steps[0]["send"], False)
        self.assertEqual(steps[0]["message"], "hello")
    def test_parse_phone_contact(self):
        steps = agent.parse_steps_local("whatsapp pe 919876543210 ko message karo hello ji")
        self.assertEqual(steps[0]["contact"], "919876543210")
        self.assertEqual(steps[0]["message"], "hello ji")
    def test_parse_unknown_is_empty(self):
        self.assertEqual(agent.parse_steps_local("aaj mausam kaisa hai"), [])
    def test_parse_whatsapp_open_karke(self):
        steps = agent.parse_steps_local("chrome open karo, whatsapp open karke rahul ko message karo happy birthday aur enter press karo")
        self.assertEqual(steps, [{"action": "open_app", "name": "chrome"},
                                 {"action": "whatsapp", "contact": "rahul", "message": "happy birthday", "send": True}])
    def test_parse_chrome_then_two_more(self):
        steps = agent.parse_steps_local("chrome kholke google pe jarvis github search karo aur notepad kholo")
        self.assertEqual([s["action"] for s in steps], ["open_app", "search_google", "open_app"])
        self.assertEqual(steps[1]["query"], "jarvis github")

    # ---------------- brain-written JSON plan
    def test_plan_json_parsing(self):
        agent.gen = lambda prompt: 'Sure! Here is the plan:\n[{"action":"open_app","name":"chrome"},{"action":"play_youtube","query":"kesariya"},{"action":"hack"}]'
        steps = agent.plan_steps("chrome kholke kesariya chalao")
        self.assertEqual([s["action"] for s in steps], ["open_app", "play_youtube"])  # invalid action dropped
    def test_plan_bad_json_falls_back(self):
        agent.gen = lambda prompt: "I cannot do that"
        steps = agent.plan_steps("youtube pe lofi chalao")
        self.assertEqual(steps, [{"action": "play_youtube", "query": "lofi"}])
    def test_plan_gen_error_falls_back(self):
        def boom(prompt): raise RuntimeError("offline")
        agent.gen = boom
        steps = agent.plan_steps("youtube pe lofi chalao")
        self.assertEqual(steps, [{"action": "play_youtube", "query": "lofi"}])

    # ---------------- executor (dry run, no screen needed)
    def test_execute_order_and_summary(self):
        logs = []
        old = bus.log
        bus.log = lambda role, text: logs.append(text)
        try:
            out = agent.execute([{"action": "open_app", "name": "chrome"},
                                 {"action": "play_youtube", "query": "lofi"}], dry_run=True)
        finally:
            bus.log = old
        self.assertIn("2 steps", out)
        self.assertTrue(any("Step 1/2" in x for x in logs) and any("Step 2/2" in x for x in logs))
    def test_execute_stop_flag(self):
        calls = []
        pc.open_app = lambda name: (calls.append(name), agent.request_stop())[0] or "ok"
        out = agent.execute([{"action": "open_app", "name": "chrome"},
                             {"action": "open_app", "name": "notepad"}], dry_run=False)
        self.assertEqual(calls, ["chrome"])          # second step never ran
        self.assertIn("Rok diya", out)
    def test_execute_locked(self):
        bus.locked = True
        out = agent.execute([{"action": "open_app", "name": "chrome"}], dry_run=True)
        self.assertIn("LOCKED", out)
    def test_stop_everything(self):
        self.assertIn("Rok diya", agent.stop_everything())
        self.assertTrue(bus.stop)
        agent.clear_stop()

    # ---------------- WhatsApp safety: confirm unless 'bina puche'
    def test_whatsapp_asks_first(self):
        pc.confirm = lambda q: False
        out = agent.whatsapp_message("rahul", "happy birthday", send=True)
        self.assertIn("User said no", out)
    def test_whatsapp_confirm_yes_dry_run(self):
        asked = []
        pc.confirm = lambda q: (asked.append(q), True)[1]
        out = agent.whatsapp_message("rahul", "happy birthday", send=True)
        self.assertTrue(asked)                       # recipient + message read back
        self.assertIn("rahul", asked[0]) and self.assertIn("happy birthday", asked[0])
        self.assertIn("DRY RUN", out)
    def test_whatsapp_auto_send_skips_confirm(self):
        asked = []
        pc.confirm = lambda q: (asked.append(q), True)[1]
        out = agent.whatsapp_message("rahul", "happy birthday", send=True, auto_send=True)
        self.assertEqual(asked, [])
        self.assertIn("DRY RUN", out)
    def test_bina_puche_sets_auto_send(self):
        asked = []
        pc.confirm = lambda q: (asked.append(q), True)[1]
        out = agent.plan_and_do("whatsapp pe rahul ko hello bhej do bina puche")
        self.assertEqual(asked, [])                  # no confirmation asked
    def test_plan_and_do_full_command(self):
        out = agent.plan_and_do("chrome kholke youtube pe kesariya chalao")
        self.assertIn("2 steps", out)

    def test_agent_tools_registered(self):
        names = {t.__name__ for t in pc.TOOLS}
        for n in ("plan_and_do", "whatsapp_message", "stop_everything"):
            self.assertIn(n, names)
        from jarvis.brain import LOCAL_TOOLS
        for n in ("plan_and_do", "whatsapp_message", "stop_everything"):
            self.assertIn(n, LOCAL_TOOLS)


if __name__ == "__main__":
    unittest.main()
