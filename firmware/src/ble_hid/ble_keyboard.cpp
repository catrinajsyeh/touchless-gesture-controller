#include "ble_hid/ble_keyboard.h"

#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEHIDDevice.h>
#include <BLEServer.h>
#include <esp_gap_ble_api.h>

namespace {

constexpr uint8_t kReportId = 1;
constexpr uint16_t kHidAppearance = 0x03C1;

const uint8_t kReportMap[] = {
    0x05, 0x01, 0x09, 0x06, 0xA1, 0x01, 0x85, 0x01, 0x05, 0x07, 0x19, 0xE0, 0x29, 0xE7, 0x15, 0x00,
    0x25, 0x01, 0x75, 0x01, 0x95, 0x08, 0x81, 0x02, 0x95, 0x01, 0x75, 0x08, 0x81, 0x01, 0x95, 0x05,
    0x75, 0x01, 0x05, 0x08, 0x19, 0x01, 0x29, 0x05, 0x91, 0x02, 0x95, 0x01, 0x75, 0x03, 0x91, 0x01,
    0x95, 0x06, 0x75, 0x08, 0x15, 0x00, 0x25, 0x65, 0x05, 0x07, 0x19, 0x00, 0x29, 0x65, 0x81, 0x00,
    0xC0,
};

class ServerCallbacks : public BLEServerCallbacks {
 public:
  explicit ServerCallbacks(BleKeyboard* owner) : owner_(owner) {}

  void onConnect(BLEServer* server) override {
    (void)server;
    owner_->noteConnection(true);
  }

  void onConnect(BLEServer* server, esp_ble_gatts_cb_param_t* param) override {
    (void)server;
    (void)param;
    owner_->noteConnection(true);
  }

  void onDisconnect(BLEServer* server) override {
    (void)server;
    owner_->noteConnection(false);
  }

 private:
  BleKeyboard* owner_;
};

}  // namespace

bool BleKeyboard::begin() {
  connected_ = false;
  started_ = false;
  last_advertise_ms_ = 0;
  server_ = nullptr;
  advertising_ = nullptr;
  input_report_ = nullptr;

  BLEDevice::init("Touchless Keys");
  BLEDevice::setPower(ESP_PWR_LVL_P9);

  BLEServer* server = BLEDevice::createServer();
  server->setCallbacks(new ServerCallbacks(this));
  server_ = server;

  BLEHIDDevice* hid = new BLEHIDDevice(server);
  BLECharacteristic* input = hid->inputReport(kReportId);
  input_report_ = input;
  hid->outputReport(kReportId);
  hid->manufacturer()->setValue(std::string("Freenove"));
  hid->pnp(0x02, 0xE502, 0xA111, 0x0210);
  hid->hidInfo(0x00, 0x01);
  hid->reportMap((uint8_t*)kReportMap, sizeof(kReportMap));
  hid->startServices();
  hid->setBatteryLevel(100);

  BLESecurity* security = new BLESecurity();
  security->setAuthenticationMode(ESP_LE_AUTH_BOND);
  security->setCapability(ESP_IO_CAP_NONE);

  BLEAdvertising* advertising = server->getAdvertising();
  advertising->setAppearance(kHidAppearance);
  advertising->addServiceUUID(hid->hidService()->getUUID());
  advertising->setScanResponse(true);
  advertising->setMinInterval(32);
  advertising->setMaxInterval(64);
  advertising->start();
  advertising_ = advertising;
  started_ = true;
  last_advertise_ms_ = millis();
  return true;
}

void BleKeyboard::noteConnection(bool connected) {
  const bool was = connected_;
  connected_ = connected;
  if (was && !connected_) restartAdvertising();
}

void BleKeyboard::restartAdvertising() {
  if (advertising_ == nullptr) return;
  BLEAdvertising* advertising = (BLEAdvertising*)advertising_;
  advertising->stop();
  advertising->start();
  last_advertise_ms_ = millis();
}

bool BleKeyboard::tap(uint8_t hid_keycode) {
  if (!connected_ || input_report_ == nullptr || hid_keycode == 0) return false;
  BLECharacteristic* input = (BLECharacteristic*)input_report_;
  uint8_t pressed[8] = {0, 0, hid_keycode, 0, 0, 0, 0, 0};
  input->setValue(pressed, sizeof(pressed));
  input->notify();
  delay(30);
  uint8_t released[8] = {0, 0, 0, 0, 0, 0, 0, 0};
  input->setValue(released, sizeof(released));
  input->notify();
  return true;
}

void BleKeyboard::forget() {
  int count = esp_ble_get_bond_device_num();
  if (count > 0) {
    if (count > 16) count = 16;
    esp_ble_bond_dev_t devices[16];
    int listed = count;
    if (esp_ble_get_bond_device_list(&listed, devices) == ESP_OK) {
      for (int i = 0; i < listed; ++i) esp_ble_remove_bond_device(devices[i].bd_addr);
    }
  }
  connected_ = false;
  restartAdvertising();
}

void BleKeyboard::service() {
  if (!started_) return;
  if (!connected_ && (uint32_t)(millis() - last_advertise_ms_) > 8000) restartAdvertising();
}

const char* BleKeyboard::state() const {
  if (!started_) return "off";
  return connected_ ? "connected" : "advertising";
}
