#pragma once

#include <stdint.h>

#include "config/gesture_config.h"

// Keep this in sync with evaluation/decision_model.py.
// One accepted gesture latches until a neutral frame, and a cooldown
// blocks a second key even if the pose changes.

struct DecisionOutcome {
  bool send_key;
  const char* reason;
};

class GestureDecision {
 public:
  void reset();
  void setThreshold(float value);
  void setNeutralFloor(float value);
  void setCooldownMs(uint32_t value);
  void setEnabled(GestureId id, bool enabled);
  void setModelReady(bool ready);
  void setSuspended(bool suspended);

  float threshold() const { return threshold_; }
  float neutralFloor() const { return neutral_floor_; }
  uint32_t cooldownMs() const { return cooldown_ms_; }
  bool enabled(GestureId id) const;
  bool suspended() const { return suspended_; }
  bool modelReady() const { return model_ready_; }

  DecisionOutcome update(GestureId gesture, float confidence, uint32_t now_ms, bool ble_connected);

 private:
  void sanitize();

  float threshold_;
  float neutral_floor_;
  uint32_t cooldown_ms_;
  bool enabled_[kGestureCount];
  bool saw_neutral_;
  bool has_fired_;
  bool model_ready_;
  bool suspended_;
  GestureId last_fired_;
  uint32_t last_fire_ms_;
};
