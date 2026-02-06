import unittest
from types import SimpleNamespace

from ingenierof125.core.config import AppConfig


class TestConfigDefaults(unittest.TestCase):
    def test_defaults_exist(self):
        cfg = AppConfig.from_obj(SimpleNamespace())
        self.assertEqual(cfg.log_dir, "logs")
        self.assertEqual(cfg.queue_maxsize, 2048)
        self.assertEqual(cfg.dispatch_maxsize, 2048)
        self.assertEqual(cfg.listen, "0.0.0.0:20777")
        self.assertEqual(cfg.replay_speed, 1.0)
        self.assertEqual(cfg.packet_format, 2025)


if __name__ == "__main__":
    unittest.main(verbosity=2)
