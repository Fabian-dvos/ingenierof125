import json
import tempfile
import unittest
from pathlib import Path

from ingenierof125.rules.load import load_rules


class TestRulesBOM(unittest.TestCase):
    def test_load_rules_utf8_bom(self):
        data = {"version": 1, "hello": "world"}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "rules.json"
            # Escribir con BOM explícito
            raw = ("\ufeff" + json.dumps(data)).encode("utf-8")
            p.write_bytes(raw)

            out = load_rules(str(p))
            self.assertEqual(out["version"], 1)
            self.assertEqual(out["hello"], "world")


if __name__ == "__main__":
    unittest.main(verbosity=2)