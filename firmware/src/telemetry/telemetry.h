#pragma once

#include <stddef.h>
#include <stdint.h>

#include "config/gesture_config.h"

struct DeviceCommand {
  enum Type : uint8_t {
    kNone = 0,
    kFrame,
    kKeyTest,
    kSet,
    kGesture,
    kOrient,
    kForget,
    kStatus,
    kSuspend,
    kCrop,
    kLandmarks
  };

  Type type;
  char name[24];
  char key[16];
  float number;
  float crop_x;
  float crop_y;
  float crop_w;
  float crop_h;
  float landmarks[42];
  int landmark_count;
  int flag;
  int vflip;
  int hmirror;
  int swap;
};

struct InferenceReport {
  GestureId gesture;
  float confidence;
  const float* scores;
  uint32_t inference_us;
  uint32_t e2e_us;
  bool fired;
  const char* decision;
  const char* key_name;
};

struct StatusReport {
  bool camera_ok;
  const char* sensor_name;
  uint16_t sensor_pid;
  int frame_w;
  int frame_h;
  const char* ble_state;
  bool model_ready;
  const char* model_domain;
  uint32_t model_checksum;
  bool keys_suspended;
  bool preview_on;
  uint32_t heap_free;
  uint32_t psram_free;
  uint32_t sketch_size;
  float threshold;
  float neutral_floor;
  uint32_t cooldown_ms;
  uint32_t capture_failures;
};

class Telemetry {
 public:
  void begin();
  bool poll(DeviceCommand* command);
  void boot();
  void log(const char* level, const char* message);
  void ack(const char* command, bool ok, const char* detail);
  void status(const StatusReport& report);
  void inference(const InferenceReport& report);
  void keyEvent(const char* source, const char* key_name, const char* gesture);
  void frame(const uint8_t* gray, int width, int height);
  void frameJpeg(const uint8_t* jpeg, size_t length, int width, int height);

 private:
  bool parse(const char* line, DeviceCommand* command);
  void print(const char* line);

  char line_[900];
  int line_len_;
};
