#include "decision/gesture_decision.h"

void GestureDecision::reset() {
  threshold_ = kDefaultThreshold;
  neutral_floor_ = kDefaultNeutralFloor;
  cooldown_ms_ = kDefaultCooldownMs;
  for (int i = 0; i < kGestureCount; ++i) {
    enabled_[i] = true;
  }
  saw_neutral_ = true;
  has_fired_ = false;
  model_ready_ = false;
  suspended_ = false;
  last_fired_ = kGestureNone;
  last_fire_ms_ = 0;
}

void GestureDecision::sanitize() {
  if (threshold_ < 0.50f) threshold_ = 0.50f;
  if (threshold_ > 0.95f) threshold_ = 0.95f;
  if (neutral_floor_ < 0.05f) neutral_floor_ = 0.05f;
  if (neutral_floor_ > threshold_ - 0.05f) neutral_floor_ = threshold_ - 0.05f;
  if (cooldown_ms_ < 200) cooldown_ms_ = 200;
  if (cooldown_ms_ > 3000) cooldown_ms_ = 3000;
}

void GestureDecision::setThreshold(float value) {
  threshold_ = value;
  sanitize();
}

void GestureDecision::setNeutralFloor(float value) {
  neutral_floor_ = value;
  sanitize();
}

void GestureDecision::setCooldownMs(uint32_t value) {
  cooldown_ms_ = value;
  sanitize();
}

void GestureDecision::setEnabled(GestureId id, bool enabled) {
  if (id >= kGestureCount || id == kGestureNone) return;
  enabled_[id] = enabled;
}

void GestureDecision::setModelReady(bool ready) { model_ready_ = ready; }

void GestureDecision::setSuspended(bool suspended) { suspended_ = suspended; }

bool GestureDecision::enabled(GestureId id) const {
  if (id >= kGestureCount) return false;
  return enabled_[id];
}

DecisionOutcome GestureDecision::update(GestureId gesture, float confidence, uint32_t now_ms,
                                       bool ble_connected) {
  if (suspended_) return {false, "suspended"};
  if (!model_ready_) return {false, "untrained"};

  const bool neutral = gesture == kGestureNone || confidence < neutral_floor_;
  if (neutral) {
    saw_neutral_ = true;
    return {false, gesture == kGestureNone ? "neutral" : "uncertain"};
  }
  if (confidence < threshold_) return {false, "low_confidence"};
  if (gesture >= kGestureNone) return {false, "neutral"};
  if (!enabled_[gesture]) return {false, "disabled"};
  if (!saw_neutral_ && last_fired_ == gesture) return {false, "hold"};
  if (has_fired_ && (uint32_t)(now_ms - last_fire_ms_) < cooldown_ms_) {
    return {false, "cooldown"};
  }
  if (!ble_connected) return {false, "no_ble"};

  last_fired_ = gesture;
  saw_neutral_ = false;
  has_fired_ = true;
  last_fire_ms_ = now_ms;
  return {true, "ok"};
}
