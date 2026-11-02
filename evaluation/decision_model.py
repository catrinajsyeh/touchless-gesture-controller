"""Decision rules mirrored by firmware/src/decision/gesture_decision.cpp."""

NO_GESTURE = 4


class DecisionModel:
    def __init__(self):
        self.threshold = 0.70
        self.neutral_floor = 0.40
        self.cooldown_ms = 700
        self.enabled = [True, True, True, True, True]
        self.saw_neutral = True
        self.has_fired = False
        self.model_ready = False
        self.suspended = False
        self.last_fired = None
        self.last_fire_ms = 0

    def set_threshold(self, value):
        self.threshold = float(value)
        self._sanitize()

    def set_neutral_floor(self, value):
        self.neutral_floor = float(value)
        self._sanitize()

    def set_cooldown_ms(self, value):
        self.cooldown_ms = int(value)
        self._sanitize()

    def _sanitize(self):
        self.threshold = min(0.95, max(0.50, self.threshold))
        self.neutral_floor = min(self.threshold - 0.05, max(0.05, self.neutral_floor))
        self.cooldown_ms = min(3000, max(200, int(self.cooldown_ms)))

    def update(self, gesture, confidence, now_ms, ble_connected):
        if self.suspended:
            return False, "suspended"
        if not self.model_ready:
            return False, "untrained"
        neutral = gesture == NO_GESTURE or confidence < self.neutral_floor
        if neutral:
            self.saw_neutral = True
            return False, "neutral" if gesture == NO_GESTURE else "uncertain"
        if confidence < self.threshold:
            return False, "low_confidence"
        if gesture >= NO_GESTURE:
            return False, "neutral"
        if not self.enabled[gesture]:
            return False, "disabled"
        if (not self.saw_neutral) and self.last_fired == gesture:
            return False, "hold"
        if self.has_fired and (now_ms - self.last_fire_ms) < self.cooldown_ms:
            return False, "cooldown"
        if not ble_connected:
            return False, "no_ble"
        self.last_fired = gesture
        self.saw_neutral = False
        self.has_fired = True
        self.last_fire_ms = now_ms
        return True, "ok"
