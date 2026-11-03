# Partner boot-up guide

Use this if you are taking over the Freenove ESP32 and want to see live gestures and TikTok keys.

Repo: https://github.com/catrinajsyeh/touchless-gesture-controller

## Day-1 path (board already flashed)

Do these in order.

### 1. Plug in the board

1. Make sure the camera ribbon is fully seated.
2. Use the USB-C port labeled **UART**, not USB/OTG.
3. In Windows Device Manager → Ports, find `USB-Enhanced-SERIAL CH343 (COMx)`.
4. Remember that COM number. Examples below use `COM3`. Change it if yours is different.

### 2. Start two programs

Open two PowerShell windows in the repo folder.

Window A — website:

```powershell
cd C:\Users\Catrina\Desktop\ECE209AS\Final-Project\touchless-gesture-controller
python -m http.server 8733 --directory dashboard
```

Window B — board bridge:

```powershell
cd C:\Users\Catrina\Desktop\ECE209AS\Final-Project\touchless-gesture-controller
conda activate hand-playground
python tools/serial_bridge.py COM3
```

Good bridge message:

```text
Bridge on http://127.0.0.1:8765  serial COM3 @ 921600
```

### 3. Open the training / check window

Open http://127.0.0.1:8733

This is the UI we built for camera preview, training, and checking inference.

You should see:

- status line: **Board connected on COMx**
- left side: live camera picture from the ESP32
- green hand skeleton when a hand is found
- pose label on the picture (the board’s current guess)
- top-right tabs: **Train** and **Check**
- right side controls for the selected tab

#### What each part of the window is

| Part of the page | What it is for |
| --- | --- |
| Camera picture | Live view from the ESP32 |
| Green skeleton | Class hand finder. It marks the hand and ignores the face |
| Label on the picture | Live inference from the board model |
| **Train** tab | Save photos and train |
| **Check** tab | Watch the live guess / confidence more clearly |
| Pose buttons | Choose which gesture you are saving |
| **Save 10 photos of …** | Capture after a 3-2-1 countdown |
| **Train model** | Start training from saved photos |

#### Train tab: save gesture photos

1. Click the **Train** tab.
2. Click one pose on the right. The green one is selected.
3. Hold that pose so the green skeleton sits on your hand, not your face.
4. Click **Save 10 photos of [pose]**.
5. Wait for the countdown on the picture: **3 → 2 → 1 → Hold**.
6. Keep the pose still while it saves.
7. Repeat until each pose shows at least **20 / 20 photos**.

Poses in the UI:

| Button | How to hold it |
| --- | --- |
| Index up | Point one finger up |
| Index down | Point one finger down |
| Thumbs up | Thumb up, other fingers closed |
| Open palm | Open hand, fingers spread |
| No gesture | No hand in the picture |

Tips:

- Hold the hand closer than your face.
- Saving adds more photos. It does not erase old ones.
- **No gesture** means empty room / no hand, not a random pose.

#### Train tab: train the model

1. Make sure every pose has at least 20 photos.
2. Click **Train model**.
3. Wait for the message under the buttons. It should say training finished and may show held-out accuracy.

Live scrolling uses the **landmark model on the ESP32**. After photo training, if you also rebuild the landmark weights, flash the board again (see “Rebuild the landmark model” below).

#### Check tab: watch inference

1. Click the **Check** tab.
2. Hold a pose in front of the camera.
3. The big word is the board’s current gesture guess.
4. Confidence / scores update as you move.
5. Drop your hand between repeats.

Use **Check** to verify inference before you trust TikTok keys.

### 4. Connect Bluetooth

1. Windows Bluetooth → add device
2. Pair **Touchless Keys**
3. Leave it connected

The board is a Bluetooth keyboard. It does not open TikTok by itself.

### 5. Test scrolling

1. Open TikTok in a browser or app.
2. Click the TikTok window once so it is focused.
3. Hold **index finger up** in front of the camera.
4. Drop your hand, then try again.

| Pose | Key | TikTok |
| --- | --- | --- |
| Index up | Up arrow | Next video |
| Index down | Down arrow | Previous video |
| Thumbs up | L | Like |
| Open palm | Space | Play / pause |

If nothing happens, check Bluetooth first, then make sure TikTok is the focused window.

## First time on a new computer

Only needed once per laptop.

```powershell
conda create -n hand-playground python=3.11 -y
conda activate hand-playground
python -m pip install mediapipe==0.10.35 opencv-python numpy pillow pyserial platformio
```

Also make sure this file exists, or update the path in `tools/hand_gestures.py`:

```text
...\ECE209AS-InteractiveSystem-Workshop-main\Demo1_HandInteractionPlayground\assets\hand_landmarker.task
```

## If you need to reflash the board

Stop the bridge first. Only one program can use the COM port.

```powershell
cd C:\Users\Catrina\Desktop\ECE209AS\Final-Project\touchless-gesture-controller\firmware
conda activate hand-playground
python -m platformio run -e freenove_esp32s3_uart -t upload --upload-port COM3
```

Then start the bridge again:

```powershell
cd C:\Users\Catrina\Desktop\ECE209AS\Final-Project\touchless-gesture-controller
conda activate hand-playground
python tools/serial_bridge.py COM3
```

## Rebuild the landmark model

Live gestures use the landmark model on the ESP32 (`landmark_gestures`).

After you are happy with poses in the **Check** tab, or if inference got worse, rebuild and flash:

```powershell
cd C:\Users\Catrina\Desktop\ECE209AS\Final-Project\touchless-gesture-controller
conda activate hand-playground
python model/training/train_landmarks.py
cd firmware
python -m platformio run -e freenove_esp32s3_uart -t upload --upload-port COM3
```

Then restart the bridge and refresh http://127.0.0.1:8733.

Quick UI loop after that:

1. **Train** tab → save clear hand photos if needed
2. **Check** tab → confirm the guess looks right
3. Connect **Touchless Keys**
4. Focus TikTok and try Index up / Index down

## Who does what

| Piece | Where it runs |
| --- | --- |
| Camera capture | ESP32 |
| Hand skeleton finder | Laptop (class MediaPipe) |
| Gesture ML model | ESP32 |
| Key decision | ESP32 |
| Bluetooth keyboard key | ESP32 → Windows |
| TikTok scroll / like / pause | Focused TikTok window |

## Fixes

| Problem | Fix |
| --- | --- |
| No COM port | Use the UART USB-C port |
| Bridge says port busy / missing | Close the other `serial_bridge.py` |
| No camera picture | Bridge not running, or wrong COM port |
| No green skeleton | Put your hand closer than your face |
| Pose seen, no key | Connect **Touchless Keys**, then click TikTok |
| Save button does nothing | Bridge must be running and board connected |
| Train says still short on photos | Each pose needs at least 20 saved photos |
| Check tab stuck / old guess | Refresh the page after restarting the bridge |
| `No module named mediapipe` | Use `conda activate hand-playground` |

## Still open for the course

- Confirm TikTok scrolling with Bluetooth connected
- User study with at least 5 people: `evaluation/user_study/`
- Power measurement with a USB meter
- Final demo video / YouTube link
