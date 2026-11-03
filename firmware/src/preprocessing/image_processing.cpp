#include "preprocessing/image_processing.h"

#include "config/board_config.h"

#include <esp_heap_caps.h>
#include <img_converters.h>

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
  if (layout == kPixelsJpeg) {
    int divisor = 4;
    if (src_w / divisor < TOUCHLESS_MODEL_INPUT || src_h / divisor < TOUCHLESS_MODEL_INPUT) divisor = 2;
    if (src_w / divisor < TOUCHLESS_MODEL_INPUT || src_h / divisor < TOUCHLESS_MODEL_INPUT) divisor = 1;
    const int dw = src_w / divisor;
    const int dh = src_h / divisor;
    const jpg_scale_t scale = divisor == 4 ? JPG_SCALE_4X : divisor == 2 ? JPG_SCALE_2X : JPG_SCALE_NONE;
    static uint8_t* decoded = nullptr;
    static size_t decoded_cap = 0;
    const size_t need_rgb = (size_t)dw * dh * 2;
    if (decoded_cap < need_rgb) {
      free(decoded);
      decoded = (uint8_t*)heap_caps_malloc(need_rgb, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
      decoded_cap = decoded == nullptr ? 0 : need_rgb;
    }
    if (decoded == nullptr || !jpg2rgb565(src, src_len, decoded, scale)) return false;
    return prepareModelInput(decoded, dw, dh, need_rgb, kPixelsRgb565, false, out);
  }
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
