#pragma once

#include <stdint.h>

class BleKeyboard {
 public:
  bool begin();
  bool connected() const { return connected_; }
  bool tap(uint8_t hid_keycode);
  void forget();
  void service();
  void noteConnection(bool connected);
  const char* state() const;

 private:
  void restartAdvertising();

  bool connected_;
  bool started_;
  uint32_t last_advertise_ms_;
  void* server_;
  void* advertising_;
  void* input_report_;
};
