#include "preprocessing/image_processing.h"

#include "config/board_config.h"

namespace {

int grayFromRgb565(uint16_t pixel) {
  const int r = (pixel >> 11) & 0x1F;
  const int g = (pixel >> 5) & 0x3F;
  const int b = pixel & 0x1F;
  return (r * 255 / 31 + g * 255 / 63 + b * 255 / 31) / 3;
}

uint16_t readRgb565(const uint8_t* src, int index, bool byte_swap) {
  const uint8_t b0 = src[index];
  const uint8_t b1 = src[index + 1];
  if (byte_swap) return (uint16_t)((b0 << 8) | b1);
  return (uint16_t)(b0 | (b1 << 8));
}

}  // namespace

bool prepareModelInput(const uint8_t* src, int src_w, int src_h, size_t src_len, PixelLayout layout,
                       bool byte_swap, PreparedFrame* out) {
  if (src == nullptr || out == nullptr || src_w <= 0 || src_h <= 0) return false;
  const size_t need = layout == kPixelsRgb565 ? (size_t)src_w * src_h * 2 : (size_t)src_w * src_h;
  if (src_len < need) return false;

  constexpr int kOut = TOUCHLESS_MODEL_INPUT;
  for (int y = 0; y < kOut; ++y) {
    const int sy = y * src_h / kOut;
    for (int x = 0; x < kOut; ++x) {
      const int sx = x * src_w / kOut;
      int gray = 0;
      if (layout == kPixelsGray) {
        gray = src[sy * src_w + sx];
      } else {
        const int index = (sy * src_w + sx) * 2;
        gray = grayFromRgb565(readRgb565(src, index, byte_swap));
      }
      if (gray < 0) gray = 0;
      if (gray > 255) gray = 255;
      const int dest = y * kOut + x;
      out->preview[dest] = (uint8_t)gray;
      out->model[dest] = (float)gray * (1.0f / 127.5f) - 1.0f;
    }
  }
  out->width = kOut;
  out->height = kOut;
  return true;
}
