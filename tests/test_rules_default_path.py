import unittest

from ingenierof125.rules.load import default_rules_path


class TestDefaultRulesPath(unittest.TestCase):
    def test_default_rules_path_returns_string(self):
        p = default_rules_path()
        self.assertIsInstance(p, str)
        self.assertTrue(p.endswith("v1.json"))


if __name__ == "__main__":
    unittest.main(verbosity=2)