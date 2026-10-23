"""Unit tests for the pure parts of drive.py. Run: python3 -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import drive as D  # noqa: E402

UI = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node class="android.widget.FrameLayout" clickable="false" bounds="[0,0][1080,2340]" text="" content-desc="" resource-id="">
    <node class="android.widget.LinearLayout" clickable="true" bounds="[40,200][1040,320]" text="" content-desc="" resource-id="com.x/search_bar">
      <node class="android.widget.TextView" clickable="false" bounds="[120,230][600,290]" text="Search stocks, MF" content-desc="" resource-id=""/>
    </node>
    <node class="android.widget.ImageView" clickable="true" bounds="[900,60][1000,160]" text="" content-desc="Search" resource-id="com.x/ic_search"/>
    <node class="android.widget.TextView" clickable="false" bounds="[0,1000][1080,1060]" text="Research" resource-id="" content-desc=""/>
  </node>
</hierarchy>"""


class PromptTests(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(D.classify_prompt("→ Unlock / enter PIN. Press Enter when HOME is fully loaded. [Enter = continue, q = stop]"), "home")
        self.assertEqual(D.classify_prompt("→ Open Search. Press Enter the moment it is fully loaded. [Enter = continue, q = stop]"), "open")
        self.assertEqual(D.classify_prompt("→ Open Search. Press Enter when search results list is loaded. [Enter = continue, q = stop]"), "open")
        self.assertEqual(D.classify_prompt("→ Gestures listed above will be played on Search. Press Enter to play them (q to stop). [Enter = continue, q = stop]"), "gestures")
        self.assertEqual(D.classify_prompt("→ Go to the screen just BEFORE Search (the one you open it from). Press Enter when settled. [Enter = continue, q = stop]"), "before")
        self.assertEqual(D.classify_prompt("→ Open Search, wait for it to load, then go back (3/10). [Enter = continue, q = stop]"), "cycle")
        self.assertEqual(D.classify_prompt("→ Something new [Enter = continue, q = stop]"), "other")

    def test_prompt_regex_matches_bench_prompt_tail(self):
        self.assertTrue(D.PROMPT_RE.search("  → Open X. [Enter = continue, q = stop] "))
        self.assertFalse(D.PROMPT_RE.search("Run 1/5: coldstart, ram"))


class StepTests(unittest.TestCase):
    def test_render(self):
        self.assertEqual(D.render_step("find:{screen}", "Search", "RELIANCE"), "find:Search")
        self.assertEqual(D.render_step("text:{subject}", "Search", "RELIANCE"), "text:RELIANCE")
        self.assertEqual(D.render_step("text:{subject}", "Search", None), "text:")

    def test_parse_good(self):
        self.assertEqual(D.parse_step("find:Search"), ("find", "Search"))
        self.assertEqual(D.parse_step("tap:0.5 0.08"), ("tap", [0.5, 0.08]))
        self.assertEqual(D.parse_step("swipe:0.5 0.8 0.5 0.3"), ("swipe", [0.5, 0.8, 0.5, 0.3]))
        self.assertEqual(D.parse_step("swipe:0.5 0.8 0.5 0.3 400"), ("swipe", [0.5, 0.8, 0.5, 0.3, 400]))
        self.assertEqual(D.parse_step("key:KEYCODE_BACK"), ("key", "KEYCODE_BACK"))
        self.assertEqual(D.parse_step("sleep:2"), ("sleep", 2.0))
        self.assertEqual(D.parse_step("hide_keyboard"), ("hide_keyboard", None))

    def test_parse_bad(self):
        for bad in ("tap:0.5", "tap:1.5 0.5", "swipe:0.1 0.2 0.3", "frob:1", "find:", "nonsense"):
            with self.assertRaises(ValueError, msg=bad):
                D.parse_step(bad)

    def test_defaults_when_module_has_no_auto_open(self):
        open_steps, back = D.auto_open_steps({"name": "search"}, "Kite")
        self.assertEqual(open_steps, D.DEFAULT_OPEN)
        self.assertEqual(back, D.DEFAULT_BACK)

    def test_per_app_overrides_default(self):
        mod = {"auto_open": {"default": ["find:{screen}"], "back": ["key:KEYCODE_BACK"],
                             "per_app": {"Kite": ["tap:0.5 0.1"]}}}
        self.assertEqual(D.auto_open_steps(mod, "Kite")[0], ["tap:0.5 0.1"])
        self.assertEqual(D.auto_open_steps(mod, "Groww")[0], ["find:{screen}"])
        self.assertEqual(D.auto_open_steps(mod, "Groww")[1], ["key:KEYCODE_BACK"])

    def test_rise_aliases_share_rise_steps(self):
        mod = {"auto_open": {"per_app": {"RISE": ["tap:0.5 0.1"]}}}
        self.assertEqual(D.auto_open_steps(mod, "Riise")[0], ["tap:0.5 0.1"])


class NodeTests(unittest.TestCase):
    def test_bounds(self):
        self.assertEqual(D.parse_bounds("[40,200][1040,320]"), (540, 260))
        self.assertIsNone(D.parse_bounds("junk"))

    def test_find_prefers_exact_then_word_then_substring(self):
        nodes = D.find_nodes(UI, "search")
        self.assertEqual(len(nodes), 4)
        self.assertEqual(nodes[0]["value"], "Search")           # exact content-desc, clickable icon
        self.assertEqual(nodes[1]["value"], "com.x/search_bar")  # whole word, clickable
        self.assertEqual(nodes[2]["value"], "Search stocks, MF")  # whole word, via clickable parent
        self.assertTrue(nodes[2]["via_parent"])
        self.assertEqual(nodes[2]["center"], (540, 260))          # tapped at its clickable parent
        self.assertEqual(nodes[3]["value"], "Research")           # substring only, last

    def test_find_is_case_insensitive_and_empty_on_miss(self):
        self.assertEqual(D.find_nodes(UI, "RESEARCH")[0]["value"], "Research")
        self.assertEqual(D.find_nodes(UI, "Portfolio"), [])
        self.assertEqual(D.find_nodes("<not xml", "x"), [])


class ScreenTests(unittest.TestCase):
    def test_auth_detection(self):
        self.assertTrue(D.is_auth_screen("", "Enter your 4-digit PIN | Forgot PIN?"))
        self.assertTrue(D.is_auth_screen("mCurrentFocus=Window{1 u0 com.x/com.x.LoginActivity}", "Welcome"))
        self.assertTrue(D.is_auth_screen(
            "mCurrentFocus=Window{2 u0 com.google.android.gms/com.google.android.gms.common.account.AccountPickerActivity}", ""))
        self.assertFalse(D.is_auth_screen("mCurrentFocus=Window{1 u0 com.x/com.x.MainActivity}", "Portfolio | Watchlist"))

    def test_keyboard(self):
        self.assertTrue(D.keyboard_shown("  mInputShown=true mShowRequested=true"))
        self.assertFalse(D.keyboard_shown("  mInputShown=false"))
        self.assertFalse(D.keyboard_shown(""))


if __name__ == "__main__":
    unittest.main()
