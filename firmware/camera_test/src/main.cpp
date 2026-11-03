#include <WiFi.h>
#include <WebServer.h>
#include <esp_camera.h>

// Freenove ESP32-S3-WROOM camera connector (CAMERA_MODEL_ESP32S3_EYE).
#define PWDN_GPIO_NUM -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 15
#define SIOD_GPIO_NUM 4
#define SIOC_GPIO_NUM 5
#define Y9_GPIO_NUM 16
#define Y8_GPIO_NUM 17
#define Y7_GPIO_NUM 18
#define Y6_GPIO_NUM 12
#define Y5_GPIO_NUM 10
#define Y4_GPIO_NUM 8
#define Y3_GPIO_NUM 9
#define Y2_GPIO_NUM 11
#define VSYNC_GPIO_NUM 6
#define HREF_GPIO_NUM 7
#define PCLK_GPIO_NUM 13

static const char* kSsid = "Touchless-Cam";
static const char* kPassword = "viewcamera";

WebServer server(80);

bool startCamera(uint32_t xclk_hz) {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = xclk_hz;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 10;
  config.fb_count = 1;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.grab_mode = CAMERA_GRAB_LATEST;

  if (esp_camera_init(&config) != ESP_OK) return false;

  sensor_t* sensor = esp_camera_sensor_get();
  if (sensor != nullptr) {
    sensor->set_framesize(sensor, FRAMESIZE_VGA);
    sensor->set_quality(sensor, 10);
    sensor->set_whitebal(sensor, 1);
    sensor->set_exposure_ctrl(sensor, 1);
    sensor->set_gain_ctrl(sensor, 1);
  }
  return true;
}

void handleJpg() {
  camera_fb_t* frame = esp_camera_fb_get();
  if (frame == nullptr) {
    server.send(503, "text/plain", "no frame");
    return;
  }
  server.sendHeader("Cache-Control", "no-store");
  server.send_P(200, "image/jpeg", (const char*)frame->buf, frame->len);
  esp_camera_fb_return(frame);
}

void handleRoot() {
  server.send(200, "text/html",
              "<!DOCTYPE html><html><head><meta name=viewport content=\"width=device-width\">"
              "<title>Camera test</title><style>body{margin:0;background:#111}img{width:100%;height:auto}</style></head>"
              "<body><img id=v alt=camera><script>function tick(){v.src='/jpg?t='+Date.now()}"
              "tick();setInterval(tick,400)</script></body></html>");
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("camera test: gesture model is not running");

  bool ready = startCamera(20000000);
  if (!ready) {
    esp_camera_deinit();
    ready = startCamera(10000000);
  }
  if (!ready) {
    Serial.println("camera failed to start");
    return;
  }

  sensor_t* sensor = esp_camera_sensor_get();
  Serial.printf("camera ready pid 0x%04x\n", sensor == nullptr ? 0 : sensor->id.PID);

  WiFi.mode(WIFI_AP);
  WiFi.setSleep(false);
  WiFi.softAP(kSsid, kPassword);
  Serial.print("join Wi-Fi ");
  Serial.print(kSsid);
  Serial.print(" password ");
  Serial.print(kPassword);
  Serial.print(" then open http://");
  Serial.println(WiFi.softAPIP());

  server.on("/", handleRoot);
  server.on("/jpg", handleJpg);
  server.begin();
}

void loop() {
  server.handleClient();
}
