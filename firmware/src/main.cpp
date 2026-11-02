#include <Arduino.h>
#include <stdio.h>
#include <string.h>

#include "ble_hid/ble_keyboard.h"
#include "camera/camera_manager.h"
#include "config/board_config.h"
#include "config/gesture_config.h"
#include "decision/gesture_decision.h"
#include "gesture_recognition/gesture_classifier.h"
#include "preprocessing/image_processing.h"
#include "telemetry/telemetry.h"

namespace {

Telemetry g_telemetry;
CameraManager g_camera;
BleKeyboard g_keyboard;
GestureDecision g_decision;
GestureClassifier g_classifier;
PreparedFrame g_prepared;

bool g_preview = true;
bool g_swap = false;
bool g_saw_frame = false;
uint32_t g_last_status_ms = 0;
uint32_t g_last_preview_ms = 0;
bool g_want_frame = false;

void setLed(bool on) {
  const bool level = TOUCHLESS_LED_ACTIVE_HIGH ? on : !on;
  digitalWrite(TOUCHLESS_LED_GPIO, level ? HIGH : LOW);
}

void blink(int count, int on_ms, int off_ms) {
  for (int i = 0; i < count; ++i) {
    setLed(true);
    delay(on_ms);
    setLed(false);
    delay(off_ms);
  }
}

GestureId gestureFromName(const char* name) {
  for (int i = 0; i < kGestureCount; ++i) {
    if (strcmp(kBindings[i].name, name) == 0) return kBindings[i].id;
  }
  return kGestureCount;
}

uint8_t hidFromTestKey(const char* key) {
  if (strcmp(key, "up") == 0) return kHidArrowUp;
  if (strcmp(key, "down") == 0) return kHidArrowDown;
  if (strcmp(key, "l") == 0) return kHidKeyL;
  if (strcmp(key, "space") == 0) return kHidSpace;
  return 0;
}

const char* testKeyName(const char* key) {
  if (strcmp(key, "up") == 0) return "ArrowUp";
  if (strcmp(key, "down") == 0) return "ArrowDown";
  if (strcmp(key, "l") == 0) return "KeyL";
  if (strcmp(key, "space") == 0) return "Space";
  return "";
}

void publishStatus() {
  StatusReport report = {};
  report.camera_ok = g_camera.ok();
  report.sensor_name = g_camera.sensorName();
  report.sensor_pid = g_camera.sensorPid();
  report.frame_w = g_camera.frameWidth();
  report.frame_h = g_camera.frameHeight();
  report.ble_state = g_keyboard.state();
  report.model_ready = g_classifier.ready();
  report.model_domain = g_classifier.domain();
  report.model_checksum = g_classifier.checksum();
  report.keys_suspended = g_decision.suspended();
  report.preview_on = g_preview;
  report.heap_free = ESP.getFreeHeap();
  report.psram_free = ESP.getFreePsram();
  report.sketch_size = ESP.getSketchSize();
  report.threshold = g_decision.threshold();
  report.neutral_floor = g_decision.neutralFloor();
  report.cooldown_ms = g_decision.cooldownMs();
  report.capture_failures = g_camera.captureFailures();
  g_telemetry.status(report);
}

void handle(const DeviceCommand& command) {
  switch (command.type) {
    case DeviceCommand::kFrame:
      g_want_frame = true;
      g_telemetry.ack("frame", g_camera.ok(), g_camera.ok() ? "queued" : "camera_off");
      break;
    case DeviceCommand::kKeyTest: {
      const uint8_t hid = hidFromTestKey(command.key);
      if (hid == 0) {
        g_telemetry.ack("keytest", false, "unknown_key");
        break;
      }
      if (!g_keyboard.connected()) {
        g_telemetry.ack("keytest", false, "no_ble");
        break;
      }
      const bool sent = g_keyboard.tap(hid);
      g_telemetry.ack("keytest", sent, sent ? "sent" : "failed");
      if (sent) g_telemetry.keyEvent("manual", testKeyName(command.key), "MANUAL");
      break;
    }
    case DeviceCommand::kSet:
      if (strcmp(command.name, "threshold") == 0) g_decision.setThreshold(command.number);
      else if (strcmp(command.name, "neutral_floor") == 0) g_decision.setNeutralFloor(command.number);
      else if (strcmp(command.name, "cooldown_ms") == 0) g_decision.setCooldownMs((uint32_t)command.number);
      else if (strcmp(command.name, "preview") == 0) g_preview = command.number >= 0.5f;
      else {
        g_telemetry.ack("set", false, "unknown");
        break;
      }
      g_telemetry.ack("set", true, command.name);
      break;
    case DeviceCommand::kGesture: {
      const GestureId id = gestureFromName(command.name);
      if (id >= kGestureNone) {
        g_telemetry.ack("gesture", false, "unknown");
        break;
      }
      g_decision.setEnabled(id, command.flag != 0);
      g_telemetry.ack("gesture", true, command.name);
      break;
    }
    case DeviceCommand::kOrient:
      g_swap = command.swap != 0;
      g_camera.setOrientation(command.vflip != 0, command.hmirror != 0);
      g_telemetry.ack("orient", true, "ok");
      break;
    case DeviceCommand::kForget:
      g_keyboard.forget();
      g_telemetry.ack("forget", true, "bonds_cleared");
      break;
    case DeviceCommand::kStatus:
      publishStatus();
      g_telemetry.ack("status", true, "ok");
      break;
    case DeviceCommand::kSuspend:
      g_decision.setSuspended(command.number >= 0.5f);
      g_telemetry.ack("suspend", true, g_decision.suspended() ? "paused" : "live");
      break;
    case DeviceCommand::kNone:
      break;
  }
}

void runVision() {
  CameraSnapshot snapshot = {};
  if (!g_camera.capture(&snapshot)) {
    g_telemetry.log("error", "Camera capture returned no frame.");
    return;
  }
  const uint32_t started = micros();
  const bool prepared = prepareModelInput(snapshot.data, snapshot.width, snapshot.height, snapshot.length,
                                          snapshot.layout, g_swap, &g_prepared);
  g_camera.release();
  if (!prepared) {
    g_telemetry.log("error", "Could not scale this frame to the model input.");
    return;
  }
  if (!g_saw_frame) {
    uint32_t checksum = 0;
    for (int i = 0; i < TOUCHLESS_MODEL_INPUT * TOUCHLESS_MODEL_INPUT; ++i) checksum += g_prepared.preview[i];
    char message[96];
    snprintf(message, sizeof(message), "Camera frame %dx%d scaled to %d checksum %lu", snapshot.width, snapshot.height,
             TOUCHLESS_MODEL_INPUT, (unsigned long)checksum);
    g_telemetry.log("info", message);
    g_saw_frame = true;
    setLed(true);
  }

  const uint32_t infer_started = micros();
  const Classification result = g_classifier.classify(g_prepared.model);
  const uint32_t inference_us = micros() - infer_started;
  const DecisionOutcome outcome =
      g_decision.update(result.id, result.confidence, millis(), g_keyboard.connected());

  bool fired = false;
  const char* key_name = "";
  if (outcome.send_key) {
    const GestureBinding& binding = kBindings[result.id];
    fired = g_keyboard.tap(binding.hid);
    key_name = binding.key_name;
    if (fired) {
      g_telemetry.keyEvent("gesture", key_name, binding.name);
      setLed(true);
    }
  }

  InferenceReport report = {};
  report.gesture = result.model_ready ? result.id : kGestureNone;
  report.confidence = result.confidence;
  report.scores = result.scores;
  report.inference_us = inference_us;
  report.e2e_us = fired ? (micros() - started) : 0;
  report.fired = fired;
  report.decision = outcome.reason;
  report.key_name = key_name;
  g_telemetry.inference(report);

  const uint32_t now = millis();
  if (g_want_frame || (g_preview && (uint32_t)(now - g_last_preview_ms) > 700)) {
    g_telemetry.frame(g_prepared.preview, g_prepared.width, g_prepared.height);
    g_last_preview_ms = now;
    g_want_frame = false;
  }
  setLed(false);
}

}  // namespace

void setup() {
  Serial.begin(TOUCHLESS_BAUD);
  delay(400);
  pinMode(TOUCHLESS_LED_GPIO, OUTPUT);
  setLed(false);
  g_telemetry.begin();
  g_decision.reset();
  g_telemetry.boot();

  if (!g_camera.begin()) {
    g_telemetry.log("error", g_camera.error());
    blink(6, 80, 80);
  } else {
    char message[96];
    snprintf(message, sizeof(message), "Camera ready, sensor %s pid 0x%04X", g_camera.sensorName(),
             g_camera.sensorPid());
    g_telemetry.log("info", message);
    blink(2, 120, 120);
  }

  g_keyboard.begin();
  const bool model_ok = g_classifier.begin();
  g_decision.setModelReady(model_ok);
  if (!model_ok) {
    g_telemetry.log("info", "Gesture model is not trained. Keys from gestures stay off until you train and reflash.");
  }
  g_telemetry.log("info", "Bluetooth keyboard is advertising as Touchless Keys.");
  publishStatus();
}

void loop() {
  g_keyboard.service();
  DeviceCommand command = {};
  while (g_telemetry.poll(&command)) handle(command);

  if (g_camera.ok()) {
    static uint32_t last_vision_ms = 0;
    if ((uint32_t)(millis() - last_vision_ms) >= 90) {
      runVision();
      last_vision_ms = millis();
    }
  } else if (g_want_frame) {
    g_want_frame = false;
  } else {
    setLed(((millis() / 150) % 2) == 0);
    delay(40);
  }

  if ((uint32_t)(millis() - g_last_status_ms) > 1000) {
    publishStatus();
    g_last_status_ms = millis();
  }
}
