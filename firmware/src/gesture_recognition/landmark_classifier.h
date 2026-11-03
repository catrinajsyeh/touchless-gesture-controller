#pragma once

#include "config/gesture_config.h"

#include "gesture_recognition/gesture_classifier.h"

class LandmarkClassifier {
 public:
  bool begin();
  Classification classify(const float* features42);
  bool ready() const { return ready_; }
  const char* domain() const;
  uint32_t checksum() const;

 private:
  bool ready_;
};
