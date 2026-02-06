import unittest

from dataclasses import dataclass

from ingenierof125.engine.detector import EventDetector
from ingenierof125.rules.model import RuleConfig


@dataclass
class Box:
    value: object | None = None


@dataclass
class Damage:
    front_left_wing: int = 0
    front_right_wing: int = 0


@dataclass
class Status:
    fuel_remaining_laps: float = 99.0
    penalty_seconds: float = 0.0


@dataclass
class State:
    damage: Box
    status: Box


class TestDetectorWing(unittest.TestCase):
    def test_wing_damage_event(self):
        cfg = RuleConfig(
            version="v1",
            comms_throttle_s=0,
            event_cooldown_s={"wing_damage": 0},
            thresholds={"wing_damage_warn": 25, "wing_damage_critical": 60},
        )
        det = EventDetector(cfg)
        st = State(
            damage=Box(Damage(front_left_wing=53, front_right_wing=0)),
            status=Box(Status(fuel_remaining_laps=3.0, penalty_seconds=0.0)),
        )
        evs = det.detect(st)
        self.assertTrue(any(e.key == "wing_damage" for e in evs))


if __name__ == "__main__":
    unittest.main(verbosity=2)
