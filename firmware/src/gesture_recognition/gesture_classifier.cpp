#include "gesture_recognition/gesture_classifier.h"

#include "gesture_recognition/model_weights.h"

#include <esp_heap_caps.h>
#include <math.h>
#include <stdlib.h>

namespace {

void expand(float* dest, const int8_t* src, int count, float scale) {
  for (int i = 0; i < count; ++i) dest[i] = (float)src[i] * scale;
}

void conv3s2(const float* input, int in_c, int in_h, int in_w, const float* weight, const float* bias,
             int out_c, float* output) {
  const int out_h = (in_h - 3) / 2 + 1;
  const int out_w = (in_w - 3) / 2 + 1;
  for (int oc = 0; oc < out_c; ++oc) {
    for (int oy = 0; oy < out_h; ++oy) {
      for (int ox = 0; ox < out_w; ++ox) {
        float acc = bias[oc];
        for (int ic = 0; ic < in_c; ++ic) {
          for (int ky = 0; ky < 3; ++ky) {
            const int iy = oy * 2 + ky;
            const float* row = input + ((ic * in_h + iy) * in_w);
            const float* kernel = weight + (((oc * in_c + ic) * 3 + ky) * 3);
            acc += row[ox * 2] * kernel[0];
            acc += row[ox * 2 + 1] * kernel[1];
            acc += row[ox * 2 + 2] * kernel[2];
          }
        }
        output[(oc * out_h + oy) * out_w + ox] = acc > 0.0f ? acc : 0.0f;
      }
    }
  }
}

void quadrantPool(const float* input, int channels, int height, int width, float* output) {
  const int mid_h = height / 2;
  const int mid_w = width / 2;
  for (int c = 0; c < channels; ++c) {
    float sum[4] = {0, 0, 0, 0};
    int count[4] = {0, 0, 0, 0};
    for (int y = 0; y < height; ++y) {
      for (int x = 0; x < width; ++x) {
        const int region = (y >= mid_h ? 2 : 0) + (x >= mid_w ? 1 : 0);
        sum[region] += input[(c * height + y) * width + x];
        count[region] += 1;
      }
    }
    for (int region = 0; region < 4; ++region) {
      output[region * channels + c] = sum[region] / (float)count[region];
    }
  }
}

void dense(const float* input, int in_c, const float* weight, const float* bias, int out_c, float* logits) {
  for (int oc = 0; oc < out_c; ++oc) {
    float acc = bias[oc];
    const float* row = weight + oc * in_c;
    for (int i = 0; i < in_c; ++i) acc += input[i] * row[i];
    logits[oc] = acc;
  }
}

void softmax(float* values, int count) {
  float max_value = values[0];
  for (int i = 1; i < count; ++i) {
    if (values[i] > max_value) max_value = values[i];
  }
  float sum = 0.0f;
  for (int i = 0; i < count; ++i) {
    values[i] = expf(values[i] - max_value);
    sum += values[i];
  }
  if (sum <= 0.0f) sum = 1.0f;
  for (int i = 0; i < count; ++i) values[i] /= sum;
}

Classification blank() {
  Classification result = {};
  result.id = kGestureNone;
  result.confidence = 0.0f;
  result.model_ready = false;
  result.checksum = kModelChecksum;
  return result;
}

}  // namespace

float* GestureClassifier::allocFloats(int count) {
  const size_t bytes = (size_t)count * sizeof(float);
  float* block = (float*)heap_caps_malloc(bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (block == nullptr) block = (float*)malloc(bytes);
  return block;
}

bool GestureClassifier::begin() {
  ready_ = false;
  w1_ = b1_ = w2_ = b2_ = w3_ = b3_ = wd_ = bd_ = a1_ = a2_ = a3_ = pooled_ = nullptr;
  const int w1 = kFilters1 * 3 * 3;
  const int w2 = kFilters2 * kFilters1 * 3 * 3;
  const int w3 = kFilters3 * kFilters2 * 3 * 3;
  const int wd = kGestureCount * kFilters3 * kPoolRegions;
  if (!kModelTrained) return false;
  if (kW1Count != w1 || kB1Count != kFilters1 || kW2Count != w2 || kB2Count != kFilters2 ||
      kW3Count != w3 || kB3Count != kFilters3 || kWdCount != wd || kBdCount != kGestureCount) {
    return false;
  }
  w1_ = allocFloats(w1);
  b1_ = allocFloats(kFilters1);
  w2_ = allocFloats(w2);
  b2_ = allocFloats(kFilters2);
  w3_ = allocFloats(w3);
  b3_ = allocFloats(kFilters3);
  wd_ = allocFloats(wd);
  bd_ = allocFloats(kGestureCount);
  a1_ = allocFloats(kConvOut1 * kConvOut1 * kFilters1);
  a2_ = allocFloats(kConvOut2 * kConvOut2 * kFilters2);
  a3_ = allocFloats(kConvOut3 * kConvOut3 * kFilters3);
  pooled_ = allocFloats(kFilters3 * kPoolRegions);
  if (w1_ == nullptr || b1_ == nullptr || w2_ == nullptr || b2_ == nullptr || w3_ == nullptr ||
      b3_ == nullptr || wd_ == nullptr || bd_ == nullptr || a1_ == nullptr || a2_ == nullptr ||
      a3_ == nullptr || pooled_ == nullptr) {
    return false;
  }
  expand(w1_, kW1q, w1, kW1Scale);
  expand(b1_, kB1q, kFilters1, kB1Scale);
  expand(w2_, kW2q, w2, kW2Scale);
  expand(b2_, kB2q, kFilters2, kB2Scale);
  expand(w3_, kW3q, w3, kW3Scale);
  expand(b3_, kB3q, kFilters3, kB3Scale);
  expand(wd_, kWdq, wd, kWdScale);
  expand(bd_, kBdq, kGestureCount, kBdScale);
  ready_ = true;
  return true;
}

const char* GestureClassifier::domain() const { return kModelDomain; }

uint32_t GestureClassifier::checksum() const { return kModelChecksum; }

Classification GestureClassifier::classify(const float* input) {
  if (!ready_ || input == nullptr || a1_ == nullptr) return blank();

  float* a1 = a1_;
  float* a2 = a2_;
  float* a3 = a3_;
  float* pooled = pooled_;

  conv3s2(input, 1, kModelInput, kModelInput, w1_, b1_, kFilters1, a1);
  conv3s2(a1, kFilters1, kConvOut1, kConvOut1, w2_, b2_, kFilters2, a2);
  conv3s2(a2, kFilters2, kConvOut2, kConvOut2, w3_, b3_, kFilters3, a3);
  quadrantPool(a3, kFilters3, kConvOut3, kConvOut3, pooled);

  Classification result = {};
  dense(pooled, kFilters3 * kPoolRegions, wd_, bd_, kGestureCount, result.scores);
  softmax(result.scores, kGestureCount);

  int best = 0;
  for (int i = 1; i < kGestureCount; ++i) {
    if (result.scores[i] > result.scores[best]) best = i;
  }
  result.id = (GestureId)best;
  result.confidence = result.scores[best];
  result.model_ready = true;
  result.checksum = kModelChecksum;
  return result;
}
