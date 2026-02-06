import unittest
from types import SimpleNamespace
from unittest import mock

from ingenierof125.core.logging_setup import setup_logging


class TestLoggingSetupDefaults(unittest.TestCase):
    def test_missing_log_dir_does_not_crash(self):
        cfg = SimpleNamespace(log_level="INFO")  # sin log_dir
        with mock.patch("ingenierof125.core.logging_setup.Path.mkdir") as _mk, \
             mock.patch("ingenierof125.core.logging_setup.RotatingFileHandler") as _fh:
            setup_logging(cfg)

        self.assertTrue(hasattr(cfg, "log_dir"))
        self.assertEqual(cfg.log_dir, "logs")


if __name__ == "__main__":
    unittest.main(verbosity=2)
