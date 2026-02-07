import json
import tempfile
import unittest
from pathlib import Path

from ingenierof125.rules.load import load_rules
from ingenierof125.rules.model import RulesConfig


class TestRulesConfig(unittest.TestCase):
    def test_rules_config_override_and_mapping(self):
        rc = RulesConfig({"a": 1})
        self.assertEqual(rc["a"], 1)
        rc2 = rc.override(a=2, b=3)
        self.assertEqual(rc2["a"], 2)
        self.assertEqual(rc2.get("b"), 3)

    def test_load_rules_returns_rulesconfig_and_bom_ok(self):
        data = {"version": 1, "hello": "world"}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "rules.json"
            raw = ("\ufeff" + json.dumps(data)).encode("utf-8")  # BOM
            p.write_bytes(raw)
            out = load_rules(str(p))
            self.assertIsInstance(out, RulesConfig)
            self.assertEqual(out["version"], 1)
            self.assertEqual(out["hello"], "world")


if __name__ == "__main__":
    unittest.main(verbosity=2)