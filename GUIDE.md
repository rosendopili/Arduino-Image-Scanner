# Tricorder

Point the TinyML kit camera at something, press Scan, and Gemma on the Uno Q writes a one-line away-team report. The Mac only carries the camera frame over USB and shows the page.

No wires run between the Nano and the Uno Q. Leave Arduino App Lab closed while Gemma is running. The model needs the board's memory.

## Hardware

1. Seat the Nano in the TinyML shield's two 1x15 headers with the USB silkscreen lined up.
2. Seat the OV7675 in the shield's 2x10 header, lens farther from the Nano, pins fully in.
3. Plug the Nano into the Mac. The green power LED stays on.
4. Leave the Uno Q on Wi-Fi (`roarduino.local`, currently `192.168.1.12`).

## One-time setup on the Mac

From this project directory:

```sh
python3 -m venv .venv
.venv/bin/pip install -r mac/requirements.txt
```

Install the Nano core if it is not already installed:

```sh
./tools/arduino-cli core update-index
./tools/arduino-cli core install arduino:mbed_nano
```

The Library Manager copy of `Arduino_OV767X` (0.0.2) cannot start an OV7675. Use the current GitHub copy:

```sh
curl -fsSL -o /tmp/ov767x.zip https://github.com/arduino-libraries/Arduino_OV767X/archive/refs/heads/master.zip
rm -rf "$HOME/Documents/Arduino/libraries/Arduino_OV767X"
unzip -q /tmp/ov767x.zip -d /tmp
mv /tmp/Arduino_OV767X-master "$HOME/Documents/Arduino/libraries/Arduino_OV767X"
```

Find the Nano's port (`/dev/cu.usbmodem…`), then compile and upload:

```sh
./tools/arduino-cli compile --fqbn arduino:mbed_nano:nano33ble nano/tricorder_cam
./tools/arduino-cli upload -p /dev/cu.usbmodem31201 --fqbn arduino:mbed_nano:nano33ble nano/tricorder_cam
```

Replace the port if yours is different. A harmless warning that the camera library says `mbed` rather than `mbed_nano` can be ignored.

## What must already be on the Uno Q

These files are already on this board:

- `/home/arduino/models/gemma-4-E2B-it-Q4_K_M.gguf`
- `/home/arduino/models/mmproj-gemma-4-E2B-it-Q8_0.gguf`
- `/home/arduino/llama.cpp/build/bin/llama-server`

The vision projector, if it is ever missing, is this file:

```sh
curl -L -o /home/arduino/models/mmproj-gemma-4-E2B-it-Q8_0.gguf \
  https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF/resolve/main/mmproj-gemma-4-E2B-it-Q8_0.gguf
```

Copy the viewscreen onto the board (password login as `arduino` is fine):

```sh
ssh arduino@roarduino.local 'mkdir -p ~/tricorder/static'
scp unoq/tricorder.py unoq/start-gemma.sh arduino@roarduino.local:~/tricorder/
scp unoq/static/index.html arduino@roarduino.local:~/tricorder/static/index.html
```

## Each time you run it

Quit App Lab first. Then, on the Uno Q, start Gemma and leave that session open:

```sh
ssh arduino@roarduino.local
~/tricorder/start-gemma.sh
```

Wait until the log says `listening on http://127.0.0.1:8080`. A line about failing to fit the model into device memory is a warning. The server continues and loads on the CPU.

In a second board session:

```sh
python3 ~/tricorder/tricorder.py
```

That prints `tricorder http://0.0.0.0:8090`.

On the Mac, from this project directory:

```sh
.venv/bin/python mac/relay.py --port /dev/cu.usbmodem31201
```

It prints `waiting for Scan on http://roarduino.local:8090`. If it says the name cannot be resolved, use the board's address instead:

```sh
.venv/bin/python mac/relay.py --host http://192.168.1.12:8090 --port /dev/cu.usbmodem31201
```

`hostname -I` on the board shows the current address. The relay may also say there was no boot banner. That is normal when the sketch is already running. It still takes the next frame.

## The scan

Open `http://roarduino.local:8090` and press Scan.

The snapshot shows up first. The sentence follows after the board finishes, on the order of a minute. A working reading looks like one sentence, for example: "The sensors detect a large, organic, and somewhat amorphous object in the foreground."

Hold the camera a few inches from the subject. A soft QCIF frame is expected. If Gemma cannot tell what it is, the sentence says what the sensors cannot resolve.

## Stop

Close the relay with Ctrl-C. On the board, Ctrl-C the viewscreen and `start-gemma.sh`.
