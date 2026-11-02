#pragma once

#include <stddef.h>
#include <stdint.h>

#include "preprocessing/image_processing.h"

struct CameraSnapshot {
  const uint8_t* data;
  size_t length;
  int width;
  int height;
  PixelLayout layout;
};

class CameraManager {
 public:
  bool begin();
  bool capture(CameraSnapshot* out);
  void release();
  void setOrientation(bool vflip, bool hmirror);

  bool ok() const { return ok_; }
  const char* error() const { return error_; }
  const char* sensorName() const { return sensor_name_; }
  uint16_t sensorPid() const { return sensor_pid_; }
  int frameWidth() const { return frame_w_; }
  int frameHeight() const { return frame_h_; }
  uint32_t captureFailures() const { return capture_failures_; }

 private:
  bool tryInit(uint32_t xclk_hz);
  void readSensor();

  bool ok_;
  bool vflip_;
  bool hmirror_;
  const char* error_;
  const char* sensor_name_;
  uint16_t sensor_pid_;
  int frame_w_;
  int frame_h_;
  uint32_t capture_failures_;
  void* held_fb_;
};
