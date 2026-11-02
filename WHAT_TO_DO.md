# What you still have to do

The software that can be written without the board is already in this repo. Both firmware images compile. Nothing has been flashed, the gesture model is still the empty placeholder, and the camera, Bluetooth, and TikTok have not been tried. Work through this list in order.

Replace `COM5` everywhere with the port Windows actually assigns (Device Manager, Ports).

## 1. Seat the camera

Plug the OV2640 ribbon into the 24-pin camera connector before you power the board. Metal contacts face the connector. If the serial log later says camera error `0x105`, the ribbon is backwards or not fully latched.

## 2. Flash the board

From the `firmware` folder, use the USB-C port that shows up as a CH343 serial device:

```bash
python -m platformio run -e freenove_esp32s3_uart -t upload --upload-port COM5
python -m platformio device monitor -e freenove_esp32s3_uart --port COM5
```

You want a JSON line that says the camera is ready. If upload works but the monitor stays silent, you are on the other USB-C port. Flash the native-USB build instead:

```bash
python -m platformio run -e freenove_esp32s3_usb -t upload --upload-port COM5
python -m platformio device monitor -e freenove_esp32s3_usb --port COM5
```

## 3. Pair Bluetooth

In Windows Bluetooth, pair the device named **Touchless Keys**. If a later attempt will not reconnect, remove it in Bluetooth settings, then press Forget in the dashboard or reboot the board.

## 4. Open the dashboard

From the repo root, in two terminals:

```bash
python -m http.server 8733 --directory dashboard
python tools/serial_bridge.py
```

Open http://127.0.0.1:8733 and switch the dashboard to **Live device**.

## 5. Check the keys before you trust the camera

Open TikTok in a browser and click the video once so the page has keyboard focus. On the dashboard, press **Send ↑**, **Send ↓**, **Send L**, and **Send Space**. Those buttons skip the camera and only check Bluetooth. Gesture keys stay off until step 7, because the model is not trained yet.

## 6. Collect photos

Quit the serial bridge first so it releases the COM port. From the repo root, collect at least 40 frames per class. Use more than one person, more than one background, and more than one lighting setup. Hold the pose about 30–60 cm from the lens. Put empty frames, faces, and other hand shapes in `NO_GESTURE`.

```bash
python tools/collect_dataset.py --label POINT_UP --count 40
python tools/collect_dataset.py --label POINT_DOWN --count 40
python tools/collect_dataset.py --label THUMBS_UP --count 40
python tools/collect_dataset.py --label OPEN_PALM --count 40
python tools/collect_dataset.py --label NO_GESTURE --count 40
```

## 7. Train and flash again

```bash
python model/training/train.py --dataset model/dataset
python -m platformio run -e freenove_esp32s3_uart -t upload --upload-port COM5
```

Use `freenove_esp32s3_usb` here if that is the environment that worked in step 2.

## 8. Try the four poses on TikTok

Click the TikTok video so it has focus. Each pose should fire once, then wait until your hand leaves the frame before the same pose can fire again.

| Pose | Key | TikTok |
| --- | --- | --- |
| Index finger up | Up arrow | Next video |
| Index finger down | Down arrow | Previous video |
| Thumbs up | L | Like |
| Open palm | Space | Play / pause |

## 9. Run the user study

Follow `evaluation/user_study/` with at least 5 people. Leave the sheet blank until the sessions actually happen.

## 10. Measure power

The chip cannot measure its own current. Use a USB power meter and fill in the blank table in `evaluation/memory_power/README.md`.

## 11. Share it with your partner

The files are only on this computer. Commit and push when you want your partner to see the repo.
