import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.decision_model import NO_GESTURE, DecisionModel


def ready():
    model = DecisionModel()
    model.model_ready = True
    return model


def test_untrained_never_fires():
    model = DecisionModel()
    fired, reason = model.update(0, 0.99, 1000, True)
    assert not fired and reason == "untrained"


def test_hold_until_neutral_and_cooldown():
    model = ready()
    fired, reason = model.update(0, 0.91, 1000, True)
    assert fired and reason == "ok"
    fired, reason = model.update(0, 0.95, 1200, True)
    assert not fired and reason == "hold"
    fired, reason = model.update(NO_GESTURE, 0.8, 1300, True)
    assert not fired and reason == "neutral"
    fired, reason = model.update(0, 0.93, 1500, True)
    assert not fired and reason == "cooldown"
    fired, reason = model.update(0, 0.93, 1700, True)
    assert fired and reason == "ok"


def test_other_gesture_respects_cooldown():
    model = ready()
    assert model.update(0, 0.9, 0, True)[0]
    fired, reason = model.update(1, 0.9, 100, True)
    assert not fired and reason == "cooldown"
    fired, reason = model.update(1, 0.9, 700, True)
    assert fired and reason == "ok"


def test_deadband_does_not_rearm():
    model = ready()
    assert model.update(2, 0.88, 0, True)[0]
    fired, reason = model.update(2, 0.55, 1000, True)
    assert not fired and reason == "low_confidence"
    fired, reason = model.update(2, 0.9, 2000, True)
    assert not fired and reason == "hold"
    fired, reason = model.update(2, 0.2, 3000, True)
    assert not fired and reason == "uncertain"
    fired, reason = model.update(2, 0.9, 4000, True)
    assert fired and reason == "ok"


def test_no_ble_and_disabled_and_suspended():
    model = ready()
    fired, reason = model.update(3, 0.9, 0, False)
    assert not fired and reason == "no_ble"
    model.enabled[3] = False
    fired, reason = model.update(3, 0.9, 0, True)
    assert not fired and reason == "disabled"
    model.enabled[3] = True
    model.suspended = True
    fired, reason = model.update(3, 0.9, 0, True)
    assert not fired and reason == "suspended"


if __name__ == "__main__":
    test_untrained_never_fires()
    test_hold_until_neutral_and_cooldown()
    test_other_gesture_respects_cooldown()
    test_deadband_does_not_rearm()
    test_no_ble_and_disabled_and_suspended()
    print("decision rules ok")
