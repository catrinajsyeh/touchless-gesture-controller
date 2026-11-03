#include "gesture_recognition/landmark_classifier.h"

#include "gesture_recognition/landmark_weights.h"

#include <math.h>
#include <string.h>

bool LandmarkClassifier::begin() {
  ready_ = kLandmarkModelTrained && kLandmarkInput == 42 && kLandmarkClasses == kGestureCount;
  return ready_;
}

const char* LandmarkClassifier::domain() const { return kLandmarkModelDomain; }

uint32_t LandmarkClassifier::checksum() const { return kLandmarkModelChecksum; }

Classification LandmarkClassifier::classify(const float* features42) {
  Classification result = {};
  result.id = kGestureNone;
  result.confidence = 0.0f;
  result.model_ready = ready_;
  if (!ready_ || features42 == nullptr) return result;

  float hidden[24];
  for (int h = 0; h < kLandmarkHidden; ++h) {
    float acc = (float)kLandmarkB1[h] * kLandmarkB1Scale;
    for (int i = 0; i < kLandmarkInput; ++i) {
      acc += features42[i] * ((float)kLandmarkW1[i * kLandmarkHidden + h] * kLandmarkW1Scale);
    }
    hidden[h] = acc > 0.0f ? acc : 0.0f;
  }

  float max_logit = -1e9f;
  for (int c = 0; c < kLandmarkClasses; ++c) {
    float acc = (float)kLandmarkB2[c] * kLandmarkB2Scale;
    for (int h = 0; h < kLandmarkHidden; ++h) {
      acc += hidden[h] * ((float)kLandmarkW2[h * kLandmarkClasses + c] * kLandmarkW2Scale);
    }
    result.scores[c] = acc;
    if (acc > max_logit) max_logit = acc;
  }

  float sum = 0.0f;
  for (int c = 0; c < kLandmarkClasses; ++c) {
    result.scores[c] = expf(result.scores[c] - max_logit);
    sum += result.scores[c];
  }
  if (sum <= 0.0f) sum = 1.0f;
  int best = 0;
  for (int c = 0; c < kLandmarkClasses; ++c) {
    result.scores[c] /= sum;
    if (result.scores[c] > result.scores[best]) best = c;
  }
  result.id = (GestureId)best;
  result.confidence = result.scores[best];
  result.checksum = kLandmarkModelChecksum;
  return result;
}
