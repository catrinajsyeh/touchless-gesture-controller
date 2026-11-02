#pragma once

#include <stdint.h>

#include "config/board_config.h"

// Class order is shared with model/training/architecture.json.
// Do not reorder these without retraining.

enum GestureId : uint8_t {
  kGesturePointUp = 0,
  kGesturePointDown = 1,
  kGestureThumbsUp = 2,
  kGestureOpenPalm = 3,
  kGestureNone = 4,
  kGestureCount = 5
};

struct GestureBinding {
  GestureId id;
  const char* name;
  const char* key_name;
  const char* tiktok;
  uint8_t hid;
  bool sends_key;
};

// USB HID keyboard usages. L is 0x0F because 'a' is 0x04.
static constexpr uint8_t kHidArrowUp = 0x52;
static constexpr uint8_t kHidArrowDown = 0x51;
static constexpr uint8_t kHidKeyL = 0x0F;
static constexpr uint8_t kHidSpace = 0x2C;

static const GestureBinding kBindings[kGestureCount] = {
    {kGesturePointUp, "POINT_UP", "ArrowUp", "Next video", kHidArrowUp, true},
    {kGesturePointDown, "POINT_DOWN", "ArrowDown", "Previous video", kHidArrowDown, true},
    {kGestureThumbsUp, "THUMBS_UP", "KeyL", "Like", kHidKeyL, true},
    {kGestureOpenPalm, "OPEN_PALM", "Space", "Play or pause", kHidSpace, true},
    {kGestureNone, "NO_GESTURE", "", "No command", 0, false},
};

static constexpr int kModelInput = TOUCHLESS_MODEL_INPUT;
static constexpr int kFilters1 = 16;
static constexpr int kFilters2 = 32;
static constexpr int kFilters3 = 48;
static constexpr int kConvOut1 = (kModelInput - 3) / 2 + 1;
static constexpr int kConvOut2 = (kConvOut1 - 3) / 2 + 1;
static constexpr int kConvOut3 = (kConvOut2 - 3) / 2 + 1;
static constexpr int kPoolRegions = 4;

static_assert(kConvOut1 == 31, "conv spatial size drifted");
static_assert(kConvOut2 == 15, "conv spatial size drifted");
static_assert(kConvOut3 == 7, "conv spatial size drifted");

static constexpr float kDefaultThreshold = 0.70f;
static constexpr float kDefaultNeutralFloor = 0.40f;
static constexpr uint32_t kDefaultCooldownMs = 700;
