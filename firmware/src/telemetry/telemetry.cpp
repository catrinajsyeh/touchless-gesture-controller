#include "telemetry/telemetry.h"

#include "config/board_config.h"

#include <Arduino.h>
#include <esp_heap_caps.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace {

const char kAlphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

bool extractString(const char* json, const char* key, char* out, int out_len) {
  char pattern[32];
  snprintf(pattern, sizeof(pattern), "\"%s\"", key);
  const char* found = strstr(json, pattern);
  if (found == nullptr) return false;
  const char* colon = strchr(found + strlen(pattern), ':');
  if (colon == nullptr) return false;
  const char* quote = strchr(colon, '"');
  if (quote == nullptr) return false;
  ++quote;
  const char* end = strchr(quote, '"');
  if (end == nullptr) return false;
  int n = (int)(end - quote);
  if (n >= out_len) n = out_len - 1;
  if (n < 0) n = 0;
  memcpy(out, quote, (size_t)n);
  out[n] = '\0';
  return true;
}

bool extractNumber(const char* json, const char* key, float* out) {
  char pattern[32];
  snprintf(pattern, sizeof(pattern), "\"%s\"", key);
  const char* found = strstr(json, pattern);
  if (found == nullptr) return false;
  const char* colon = strchr(found + strlen(pattern), ':');
  if (colon == nullptr) return false;
  ++colon;
  while (*colon == ' ') ++colon;
  char* end = nullptr;
  const float value = strtof(colon, &end);
  if (end == colon) return false;
  *out = value;
  return true;
}

}  // namespace

void Telemetry::begin() { line_len_ = 0; }

void Telemetry::print(const char* line) { Serial.println(line); }

void Telemetry::boot() {
  char buffer[192];
  snprintf(buffer, sizeof(buffer),
           "{\"type\":\"boot\",\"board\":\"Freenove ESP32-S3-WROOM\",\"camera_pins\":\"ESP32S3_EYE\","
           "\"usb\":%s,\"baud\":%d}",
#if TOUCHLESS_USB_CDC
           "\"native\"",
#else
           "\"uart\"",
#endif
           TOUCHLESS_BAUD);
  print(buffer);
}

void Telemetry::log(const char* level, const char* message) {
  char buffer[320];
  snprintf(buffer, sizeof(buffer), "{\"type\":\"log\",\"level\":\"%s\",\"msg\":\"%.220s\"}", level, message);
  print(buffer);
}

void Telemetry::ack(const char* command, bool ok, const char* detail) {
  char buffer[192];
  snprintf(buffer, sizeof(buffer), "{\"type\":\"ack\",\"cmd\":\"%s\",\"ok\":%s,\"detail\":\"%.80s\"}", command,
           ok ? "true" : "false", detail == nullptr ? "" : detail);
  print(buffer);
}

void Telemetry::status(const StatusReport& report) {
  char buffer[640];
  snprintf(buffer, sizeof(buffer),
           "{\"type\":\"status\",\"camera\":%s,\"sensor\":\"%s\",\"sensor_pid\":\"0x%04X\",\"frame_w\":%d,"
           "\"frame_h\":%d,\"ble\":\"%s\",\"model_trained\":%s,\"model_domain\":\"%s\",\"model_checksum\":%lu,"
           "\"keys_suspended\":%s,\"preview\":%s,\"heap\":%lu,\"psram\":%lu,\"sketch\":%lu,\"threshold\":%.2f,"
           "\"neutral_floor\":%.2f,\"cooldown_ms\":%lu,\"capture_failures\":%lu}",
           report.camera_ok ? "true" : "false", report.sensor_name, report.sensor_pid, report.frame_w, report.frame_h,
           report.ble_state, report.model_ready ? "true" : "false", report.model_domain,
           (unsigned long)report.model_checksum, report.keys_suspended ? "true" : "false",
           report.preview_on ? "true" : "false", (unsigned long)report.heap_free, (unsigned long)report.psram_free,
           (unsigned long)report.sketch_size, report.threshold, report.neutral_floor,
           (unsigned long)report.cooldown_ms, (unsigned long)report.capture_failures);
  print(buffer);
}

void Telemetry::inference(const InferenceReport& report) {
  char scores[96];
  scores[0] = '\0';
  if (report.scores != nullptr) {
    snprintf(scores, sizeof(scores), "[%.3f,%.3f,%.3f,%.3f,%.3f]", report.scores[0], report.scores[1],
             report.scores[2], report.scores[3], report.scores[4]);
  } else {
    snprintf(scores, sizeof(scores), "[0,0,0,0,0]");
  }
  const char* name = kBindings[report.gesture].name;
  char buffer[420];
  snprintf(buffer, sizeof(buffer),
           "{\"type\":\"inference\",\"gesture\":\"%s\",\"confidence\":%.3f,\"scores\":%s,\"inference_us\":%lu,"
           "\"e2e_us\":%lu,\"fired\":%s,\"decision\":\"%s\",\"key\":\"%s\"}",
           name, report.confidence, scores, (unsigned long)report.inference_us, (unsigned long)report.e2e_us,
           report.fired ? "true" : "false", report.decision, report.key_name == nullptr ? "" : report.key_name);
  print(buffer);
}

void Telemetry::keyEvent(const char* source, const char* key_name, const char* gesture) {
  char buffer[192];
  snprintf(buffer, sizeof(buffer), "{\"type\":\"key\",\"source\":\"%s\",\"key\":\"%s\",\"gesture\":\"%s\"}", source,
           key_name, gesture);
  print(buffer);
}

void Telemetry::frame(const uint8_t* gray, int width, int height) {
  if (gray == nullptr || width != TOUCHLESS_MODEL_INPUT || height != TOUCHLESS_MODEL_INPUT) return;
  static char encoded[5600];
  static char message[5900];
  int out = 0;
  const int length = width * height;
  for (int i = 0; i < length; i += 3) {
    const int b0 = gray[i];
    const int b1 = (i + 1 < length) ? gray[i + 1] : 0;
    const int b2 = (i + 2 < length) ? gray[i + 2] : 0;
    const int triple = (b0 << 16) | (b1 << 8) | b2;
    if (out + 4 >= (int)sizeof(encoded)) return;
    encoded[out++] = kAlphabet[(triple >> 18) & 63];
    encoded[out++] = kAlphabet[(triple >> 12) & 63];
    encoded[out++] = (i + 1 < length) ? kAlphabet[(triple >> 6) & 63] : '=';
    encoded[out++] = (i + 2 < length) ? kAlphabet[triple & 63] : '=';
  }
  encoded[out] = '\0';
  snprintf(message, sizeof(message), "{\"type\":\"frame\",\"w\":%d,\"h\":%d,\"fmt\":\"gray\",\"data\":\"%s\"}", width,
           height, encoded);
  print(message);
}

void Telemetry::frameJpeg(const uint8_t* jpeg, size_t length, int width, int height) {
  if (jpeg == nullptr || length < 32 || length > 100000) return;
  const size_t encoded_need = 4 * ((length + 2) / 3) + 1;
  const size_t message_need = encoded_need + 96;
  static char* encoded = nullptr;
  static char* message = nullptr;
  static size_t message_cap = 0;
  if (message_cap < message_need) {
    free(encoded);
    free(message);
    encoded = (char*)heap_caps_malloc(encoded_need, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    message = (char*)heap_caps_malloc(message_need, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    message_cap = (encoded != nullptr && message != nullptr) ? message_need : 0;
  }
  if (encoded == nullptr || message == nullptr) return;

  size_t out = 0;
  for (size_t i = 0; i < length; i += 3) {
    const int b0 = jpeg[i];
    const int b1 = (i + 1 < length) ? jpeg[i + 1] : 0;
    const int b2 = (i + 2 < length) ? jpeg[i + 2] : 0;
    const int triple = (b0 << 16) | (b1 << 8) | b2;
    encoded[out++] = kAlphabet[(triple >> 18) & 63];
    encoded[out++] = kAlphabet[(triple >> 12) & 63];
    encoded[out++] = (i + 1 < length) ? kAlphabet[(triple >> 6) & 63] : '=';
    encoded[out++] = (i + 2 < length) ? kAlphabet[triple & 63] : '=';
  }
  encoded[out] = '\0';
  snprintf(message, message_cap, "{\"type\":\"frame\",\"w\":%d,\"h\":%d,\"fmt\":\"jpeg\",\"data\":\"%s\"}", width,
           height, encoded);
  print(message);
}

bool Telemetry::poll(DeviceCommand* command) {
  while (Serial.available() > 0) {
    const char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c != '\n') {
      if (line_len_ < (int)sizeof(line_) - 1) {
        line_[line_len_++] = c;
      } else {
        line_len_ = 0;
      }
      continue;
    }
    line_[line_len_] = '\0';
    const int length = line_len_;
    line_len_ = 0;
    if (length > 0 && parse(line_, command)) return true;
  }
  return false;
}

bool Telemetry::parse(const char* line, DeviceCommand* command) {
  char cmd[24];
  if (!extractString(line, "cmd", cmd, (int)sizeof(cmd))) return false;
  memset(command, 0, sizeof(*command));
  command->type = DeviceCommand::kNone;
  if (strcmp(cmd, "frame") == 0) {
    command->type = DeviceCommand::kFrame;
  } else if (strcmp(cmd, "keytest") == 0) {
    command->type = DeviceCommand::kKeyTest;
    extractString(line, "key", command->key, (int)sizeof(command->key));
  } else if (strcmp(cmd, "set") == 0) {
    command->type = DeviceCommand::kSet;
    extractString(line, "name", command->name, (int)sizeof(command->name));
    extractNumber(line, "value", &command->number);
  } else if (strcmp(cmd, "gesture") == 0) {
    command->type = DeviceCommand::kGesture;
    extractString(line, "name", command->name, (int)sizeof(command->name));
    float enabled = 0;
    extractNumber(line, "enabled", &enabled);
    command->flag = enabled >= 0.5f ? 1 : 0;
  } else if (strcmp(cmd, "orient") == 0) {
    command->type = DeviceCommand::kOrient;
    float v = 0, h = 0, s = 0;
    extractNumber(line, "v", &v);
    extractNumber(line, "h", &h);
    extractNumber(line, "swap", &s);
    command->vflip = v >= 0.5f ? 1 : 0;
    command->hmirror = h >= 0.5f ? 1 : 0;
    command->swap = s >= 0.5f ? 1 : 0;
  } else if (strcmp(cmd, "forget") == 0) {
    command->type = DeviceCommand::kForget;
  } else if (strcmp(cmd, "status") == 0) {
    command->type = DeviceCommand::kStatus;
  } else if (strcmp(cmd, "suspend") == 0) {
    command->type = DeviceCommand::kSuspend;
    extractNumber(line, "value", &command->number);
  } else {
    return false;
  }
  return true;
}
