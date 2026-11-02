#pragma once

#include <stdint.h>

// Produced by model/training/export_weights.py.
// The checked-in weights are an untrained placeholder. The firmware will not
// send keys until a real gesture training run replaces this file.

extern const bool kModelTrained;
extern const char kModelDomain[];
extern const uint32_t kModelChecksum;
extern const float kInputScale;
extern const float kInputBias;

extern const int kW1Count;
extern const int8_t kW1q[];
extern const float kW1Scale;
extern const int kB1Count;
extern const int8_t kB1q[];
extern const float kB1Scale;

extern const int kW2Count;
extern const int8_t kW2q[];
extern const float kW2Scale;
extern const int kB2Count;
extern const int8_t kB2q[];
extern const float kB2Scale;

extern const int kW3Count;
extern const int8_t kW3q[];
extern const float kW3Scale;
extern const int kB3Count;
extern const int8_t kB3q[];
extern const float kB3Scale;

extern const int kWdCount;
extern const int8_t kWdq[];
extern const float kWdScale;
extern const int kBdCount;
extern const int8_t kBdq[];
extern const float kBdScale;
