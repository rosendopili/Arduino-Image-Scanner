# Tricorder

Point a TinyML-kit camera at something, press Scan, and a Gemma vision model on an Arduino Uno Q writes a one-line report. A computer in the middle only carries the camera frame over USB. The page and the model both run on the Uno Q.

Nothing is wired between the Nano and the Uno Q. They meet on the computer: the Nano sends a frame over serial, and the computer posts that frame to the board over Wi-Fi.

```
OV7675  →  Nano 33 BLE  →  USB serial  →  computer (relay.py)
                                              │
                                              ▼
                         browser  ←  Uno Q (tricorder.py + Gemma)
```

## What you need

- Arduino Nano 33 BLE, seated in the TinyML shield
- OV7675 camera in the shield's camera header
- Arduino Uno Q on the same network as the computer, with SSH login as `arduino`
- A computer with Python 3, the [Arduino CLI](https://arduino.github.io/arduino-cli/), and a USB port for the Nano
- On the Uno Q: a `llama-server` build and the two Gemma 4 E2B GGUF files listed below
- Arduino App Lab closed while Gemma is running. The model needs the board's memory.

## 1. Camera on the Nano

Seat the Nano in the shield's two 1x15 headers with the USB silkscreen lined up. Seat the OV7675 in the 2x10 header with the lens farther from the Nano and the pins fully in. Plug the Nano into the computer. The green power LED stays on.

The sketch in `nano/tricorder_cam` waits for the letter `S` on serial, then sends one QCIF RGB565 frame (176×144). That size fits the Nano. A larger color frame does not.

From this project directory, install the Mac-side dependency and the Nano core:

```sh
python3 -m venv .venv
.venv/bin/pip install -r mac/requirements.txt

arduino-cli core update-index
arduino-cli core install arduino:mbed_nano
```

The Library Manager copy of `Arduino_OV767X` (0.0.2) cannot start an OV7675. Install the current GitHub copy instead:

```sh
curl -fsSL -o /tmp/ov767x.zip https://github.com/arduino-libraries/Arduino_OV767X/archive/refs/heads/master.zip
rm -rf "$HOME/Documents/Arduino/libraries/Arduino_OV767X"
unzip -q /tmp/ov767x.zip -d /tmp
mv /tmp/Arduino_OV767X-master "$HOME/Documents/Arduino/libraries/Arduino_OV767X"
```

Find the Nano's port (`/dev/cu.usbmodem…` on macOS), then compile and upload. Replace the port with yours.

```sh
arduino-cli compile --fqbn arduino:mbed_nano:nano33ble nano/tricorder_cam
arduino-cli upload -p /dev/cu.usbmodem1101 --fqbn arduino:mbed_nano:nano33ble nano/tricorder_cam
```

A warning that the camera library says `mbed` rather than `mbed_nano` can be ignored.

Check the camera on its own, before involving the Uno Q:

```sh
.venv/bin/python mac/relay.py --port /dev/cu.usbmodem1101 --once /tmp/frame.png
```

Open that PNG. If the colors are swapped, add `--swap-bytes` here and again when you start the relay for real.

## 2. Gemma and the page on the Uno Q

`unoq/start-gemma.sh` starts a local llama.cpp server. It looks for these paths, which you can override with environment variables:

| Variable | Default |
| --- | --- |
| `LLAMA_SERVER` | `/home/arduino/llama.cpp/build/bin/llama-server` |
| `MODEL` | `/home/arduino/models/gemma-4-E2B-it-Q4_K_M.gguf` |
| `MMPROJ` | `/home/arduino/models/mmproj-gemma-4-E2B-it-Q8_0.gguf` |

The viewscreen sends images to `http://127.0.0.1:8080/v1/chat/completions`. The server has to be a build that accepts that API and a vision projector. Copy both weights onto the board if they are not already there (the projector is the smaller file):

```sh
ssh arduino@<board> 'mkdir -p ~/models'
scp gemma-4-E2B-it-Q4_K_M.gguf arduino@<board>:~/models/
scp mmproj-gemma-4-E2B-it-Q8_0.gguf arduino@<board>:~/models/
```

The projector is published with the model:

```sh
curl -L -o mmproj-gemma-4-E2B-it-Q8_0.gguf \
  https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF/resolve/main/mmproj-gemma-4-E2B-it-Q8_0.gguf
```

Use the Q4_K_M weights from that same repository for `gemma-4-E2B-it-Q4_K_M.gguf`.

Copy the viewscreen onto the board. Password login as `arduino` is enough. `<board>` is the Uno Q's mDNS name (often `*.local`) or its IP address.

```sh
ssh arduino@<board> 'mkdir -p ~/tricorder/static'
scp unoq/tricorder.py unoq/start-gemma.sh arduino@<board>:~/tricorder/
scp unoq/static/index.html arduino@<board>:~/tricorder/static/index.html
ssh arduino@<board> 'chmod +x ~/tricorder/start-gemma.sh'
```

## 3. Run it

Quit Arduino App Lab first. On the Uno Q, start Gemma and leave that session open:

```sh
ssh arduino@<board>
~/tricorder/start-gemma.sh
```

Wait until the log says the server is listening on `http://127.0.0.1:8080`. A line about failing to fit the model into device memory is a warning. The server continues and loads on the CPU.

In a second board session, start the page:

```sh
python3 ~/tricorder/tricorder.py
```

That prints `tricorder http://0.0.0.0:8090`.

On the computer, from this project directory, point the relay at the board. If you omit `--port`, it tries every `usbmodem` and `usbserial` device it can see.

```sh
.venv/bin/python mac/relay.py --host http://<board>:8090 --port /dev/cu.usbmodem1101
```

It prints `waiting for Scan on http://<board>:8090`. `hostname -I` on the board shows the current address when the name does not resolve. The relay may also say there was no boot banner. That is normal when the sketch is already running. It still takes the next frame.

Open `http://<board>:8090` and press Scan. The snapshot shows up first. The sentence follows after the board finishes, on the order of a minute. Hold the camera a few inches from the subject. A soft QCIF frame is expected.

## Make it your own

The report wording lives in the `SYSTEM` string in `unoq/tricorder.py`. The page layout and copy live in `unoq/static/index.html`. After either change, copy the file to the board again.

| What | Where |
| --- | --- |
| Page port | `TRICORDER_PORT` on the board (default `8090`) |
| Model HTTP API | `GEMMA_URL` on the board |
| Model files and `llama-server` | `MODEL`, `MMPROJ`, `LLAMA_SERVER` when starting `start-gemma.sh` |
| Board address the computer calls | `mac/relay.py --host` |
| Swapped red and blue | `mac/relay.py --swap-bytes` |

`tricorder.py` only needs the Python standard library. The computer needs `pyserial`, from `mac/requirements.txt`.

## Stop

Close the relay with Ctrl-C. On the board, Ctrl-C the viewscreen and `start-gemma.sh`.
