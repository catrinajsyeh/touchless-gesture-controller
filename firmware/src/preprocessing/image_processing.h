#pragma once

#include <stddef.h>
#include <stdint.h>

#include "config/board_config.h"

enum PixelLayout : uint8_t {
  kPixelsRgb565 = 0,
  kPixelsGray = 1
};

struct PreparedFrame {
  float model[TOUCHLESS_MODEL_INPUT * TOUCHLESS_MODEL_INPUT];
  uint8_t preview[TOUCHLESS_MODEL_INPUT * TOUCHLESS_MODEL_INPUT];
  int width;
  int height;
};

bool prepareModelInput(const uint8_t* src, int src_w, int src_h, size_t src_len, PixelLayout layout,
                       bool byte_swap, PreparedFrame* out);
