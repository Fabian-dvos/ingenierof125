import unittest

from ingenierof125.engine.events import Event, Priority
from ingenierof125.engine.priority import PriorityManager


class TestPriorityManager(unittest.TestCase):
    def test_throttle_blocks_non_urgent(self):
        pm = PriorityManager(throttle_s=10)
        t = 100.0

        e1 = Event(key="a", priority=Priority.MANAGEMENT, score=10, urgency=0, text="a", cooldown_s=0)
        e2 = Event(key="b", priority=Priority.MANAGEMENT, score=11, urgency=0, text="b", cooldown_s=0)

        pick = pm.select([e1], t)
        self.assertIsNotNone(pick)
        pm.mark_emitted(pick, t)

        pick2 = pm.select([e2], t + 5)  # dentro del throttle
        self.assertIsNone(pick2)

        pick3 = pm.select([e2], t + 11)  # pasó throttle
        self.assertIsNotNone(pick3)

    def test_urgent_bypasses_throttle(self):
        pm = PriorityManager(throttle_s=999)
        t = 50.0

        normal = Event(key="n", priority=Priority.MANAGEMENT, score=1, urgency=0, text="n", cooldown_s=0)
        urgent = Event(key="u", priority=Priority.IMMEDIATE_RISK, score=1, urgency=1, text="u", cooldown_s=0)

        pick = pm.select([normal], t)
        self.assertIsNotNone(pick)
        pm.mark_emitted(pick, t)

        pick2 = pm.select([urgent], t + 1)  # debería pasar
        self.assertIsNotNone(pick2)
        self.assertEqual(pick2.key, "u")

    def test_cooldown_blocks_same_key(self):
        pm = PriorityManager(throttle_s=0)
        t = 10.0

        e = Event(key="x", priority=Priority.IMMEDIATE_RISK, score=10, urgency=0, text="x", cooldown_s=30)
        pick = pm.select([e], t)
        self.assertIsNotNone(pick)
        pm.mark_emitted(pick, t)

        pick2 = pm.select([e], t + 5)
        self.assertIsNone(pick2)

        pick3 = pm.select([e], t + 31)
        self.assertIsNotNone(pick3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
