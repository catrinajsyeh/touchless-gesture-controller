#include "camera/camera_manager.h"

#include "config/board_config.h"

#include <Arduino.h>
#include <esp_camera.h>

namespace {

const char* nameForPid(uint16_t pid) {
  if (pid == 0x2642 || pid == 0x2641 || pid == 0x26) return "OV2640";
  if (pid == 0x3660 || pid == 0x36) return "OV3660";
  if (pid == 0x5640 || pid == 0x56) return "OV5640";
  return "unknown";
}

const char* errorText(esp_err_t err) {
  if (err == ESP_ERR_NOT_FOUND) {
    return "Camera probe failed (0x105). Reseat the OV2640 ribbon in the 24-pin connector, contacts toward the connector, then press reset.";
  }
  if (err == ESP_ERR_NO_MEM) {
    return "Camera init ran out of memory. PSRAM has to be enabled (OPI) for this board.";
  }
  return "Camera init failed.";
}

}  // namespace

bool CameraManager::begin() {
  ok_ = false;
  vflip_ = false;
  hmirror_ = false;
  error_ = "";
  sensor_name_ = "none";
  sensor_pid_ = 0;
  frame_w_ = 0;
  frame_h_ = 0;
  capture_failures_ = 0;
  held_fb_ = nullptr;

  if (!psramFound()) {
    error_ = "PSRAM was not detected. Rebuild with the Freenove environment so octal PSRAM is turned on.";
    return false;
  }

  const uint32_t clocks[] = {20000000, 10000000};
  for (uint32_t clock : clocks) {
    if (tryInit(clock)) {
      ok_ = true;
      error_ = "";
      return true;
    }
  }
  return false;
}

bool CameraManager::tryInit(uint32_t xclk_hz) {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = TOUCHLESS_Y2_GPIO;
  config.pin_d1 = TOUCHLESS_Y3_GPIO;
  config.pin_d2 = TOUCHLESS_Y4_GPIO;
  config.pin_d3 = TOUCHLESS_Y5_GPIO;
  config.pin_d4 = TOUCHLESS_Y6_GPIO;
  config.pin_d5 = TOUCHLESS_Y7_GPIO;
  config.pin_d6 = TOUCHLESS_Y8_GPIO;
  config.pin_d7 = TOUCHLESS_Y9_GPIO;
  config.pin_xclk = TOUCHLESS_XCLK_GPIO;
  config.pin_pclk = TOUCHLESS_PCLK_GPIO;
  config.pin_vsync = TOUCHLESS_VSYNC_GPIO;
  config.pin_href = TOUCHLESS_HREF_GPIO;
  config.pin_sccb_sda = TOUCHLESS_SIOD_GPIO;
  config.pin_sccb_scl = TOUCHLESS_SIOC_GPIO;
  config.pin_pwdn = TOUCHLESS_PWDN_GPIO;
  config.pin_reset = TOUCHLESS_RESET_GPIO;
  config.xclk_freq_hz = xclk_hz;
  config.pixel_format = PIXFORMAT_RGB565;
  config.frame_size = FRAMESIZE_QQVGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.grab_mode = CAMERA_GRAB_LATEST;

  const esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    error_ = errorText(err);
    return false;
  }

  readSensor();
  setOrientation(vflip_, hmirror_);
  return true;
}

void CameraManager::readSensor() {
  sensor_t* sensor = esp_camera_sensor_get();
  if (sensor == nullptr) {
    sensor_name_ = "unknown";
    sensor_pid_ = 0;
    return;
  }
  sensor_pid_ = sensor->id.PID;
  sensor_name_ = nameForPid(sensor_pid_);
  sensor->set_whitebal(sensor, 1);
  sensor->set_exposure_ctrl(sensor, 1);
  sensor->set_gain_ctrl(sensor, 1);
  sensor->set_framesize(sensor, FRAMESIZE_QQVGA);
}

void CameraManager::setOrientation(bool vflip, bool hmirror) {
  vflip_ = vflip;
  hmirror_ = hmirror;
  sensor_t* sensor = esp_camera_sensor_get();
  if (sensor == nullptr) return;
  sensor->set_vflip(sensor, vflip_ ? 1 : 0);
  sensor->set_hmirror(sensor, hmirror_ ? 1 : 0);
}

bool CameraManager::capture(CameraSnapshot* out) {
  if (out == nullptr) return false;
  if (held_fb_ != nullptr) release();
  camera_fb_t* frame = esp_camera_fb_get();
  if (frame == nullptr || frame->buf == nullptr) {
    capture_failures_++;
    if (frame != nullptr) esp_camera_fb_return(frame);
    return false;
  }
  held_fb_ = frame;
  out->data = frame->buf;
  out->length = frame->len;
  out->width = (int)frame->width;
  out->height = (int)frame->height;
  frame_w_ = out->width;
  frame_h_ = out->height;
  if (frame->format == PIXFORMAT_GRAYSCALE) {
    out->layout = kPixelsGray;
  } else if (frame->format == PIXFORMAT_RGB565) {
    out->layout = kPixelsRgb565;
  } else {
    release();
    capture_failures_++;
    return false;
  }
  return true;
}

void CameraManager::release() {
  if (held_fb_ == nullptr) return;
  esp_camera_fb_return((camera_fb_t*)held_fb_);
  held_fb_ = nullptr;
}
