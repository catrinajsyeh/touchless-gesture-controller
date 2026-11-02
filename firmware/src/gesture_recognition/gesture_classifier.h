#pragma once

#include "config/gesture_config.h"

struct Classification {
  GestureId id;
  float confidence;
  float scores[kGestureCount];
  bool model_ready;
  uint32_t checksum;
};

class GestureClassifier {
 public:
  bool begin();
  Classification classify(const float* input);
  bool ready() const { return ready_; }
  const char* domain() const;
  uint32_t checksum() const;

 private:
  float* allocFloats(int count);

  bool ready_;
  float* w1_;
  float* b1_;
  float* w2_;
  float* b2_;
  float* w3_;
  float* b3_;
  float* wd_;
  float* bd_;
  float* a1_;
  float* a2_;
  float* a3_;
  float* pooled_;
};
