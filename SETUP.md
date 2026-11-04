# Set up the tricorder from scratch

Point the TinyML-kit camera at something, press Scan, and Gemma 4 E2B on an Arduino Uno Q writes a one-line report. The computer only carries the camera frame over USB. The page and the model both run on the Uno Q.

Nothing is wired between the Nano and the Uno Q.

```
OV7675  →  Nano 33 BLE  →  USB serial  →  computer (relay.py)
                                              │
                                              ▼
                         browser  ←  Uno Q (tricorder.py + Gemma)
```

This board was named `RoArduino` and answered at `roarduino.local`. If you choose another name during setup, use that name everywhere this guide says `roarduino.local`.

Quit Arduino App Lab before you load Gemma. The model needs the board's memory.

## What you need

- Arduino Uno Q, a USB-C cable, and Arduino App Lab on the computer
- Arduino Nano 33 BLE seated in the TinyML shield
- OV7675 camera in the shield's camera header
- A computer on the same Wi-Fi network, with Python 3 and a USB port for the Nano
- This project directory

The root partition is about 5 GB. `/home/arduino` is a separate 18 GB partition (`/dev/mmcblk0p69`). Clone llama.cpp and store the weights there. The two model files together are about 3.4 GB.

## 1. Prepare the Uno Q

Install Arduino App Lab and connect the Uno Q over USB. Walk through the first-time prompts:

1. Give the board a name. This one was `RoArduino`.
2. Join the same Wi-Fi network as the computer.
3. Set a Linux password for the user `arduino`. That password is the SSH password.
4. Leave SSH enabled. App Lab turns it on as part of this setup.

When the board is on Wi-Fi, open a terminal on the computer:

```sh
ssh arduino@roarduino.local
```

If the name does not resolve, click the `>_` shell button at the bottom left of App Lab and run `hostname -I`. Use the address that is not `172.17.0.1` (that address is a local bridge on the board):

```sh
ssh arduino@192.168.1.12
```

You are done with this step when the prompt is a shell on the board.

## 2. Free disk space

On the board:

```sh
df -h / /home/arduino
```

`/home/arduino` needs several gigabytes free for the source tree and the weights. Keep the 5 GB root partition clear of model files and build output.

## 3. Build llama.cpp on the board

Stay in the SSH session. This compile uses the board's CPU. Leave it running until both targets finish.

```sh
sudo apt update
sudo apt install -y git build-essential cmake curl
```

If the blue "Daemons using outdated libraries" screen appears, press Tab to highlight `<Ok>`, then press Enter.

```sh
sudo apt clean
cd /home/arduino
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
cmake -B build
cmake --build build --config Release -j4 --target llama-cli llama-server
```

`ggerganov/llama.cpp` redirects to `ggml-org/llama.cpp`. Building from `/home/arduino` keeps the tree on the 18 GB home partition. Name both targets in one command so `llama-cli` and `llama-server` are both produced.

Confirm both programs exist:

```sh
ls -l ~/llama.cpp/build/bin/llama-cli ~/llama.cpp/build/bin/llama-server
```

`llama-server` is a small program that loads shared libraries sitting next to it. Later steps run it with `LD_LIBRARY_PATH` set to that directory. `unoq/start-gemma.sh` does that for you.

## 4. Download Gemma 4 E2B

Still on the board. The text weights are the Unsloth Q4_K_M file. The vision projector is a separate, smaller file from the ggml-org repository. Hugging Face redirects the download, so `curl` needs `-L`. `-C -` resumes a partial file if Wi-Fi drops. Run the same command again until the size matches.

```sh
mkdir -p /home/arduino/models
cd /home/arduino/models

curl -L -C - -o gemma-4-E2B-it-Q4_K_M.gguf \
  https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-Q4_K_M.gguf

curl -L -C - -o mmproj-gemma-4-E2B-it-Q8_0.gguf \
  https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF/resolve/main/mmproj-gemma-4-E2B-it-Q8_0.gguf
```

A finished pair is these exact sizes:

```sh
stat -c '%n %s' /home/arduino/models/*.gguf
```

| File | Bytes |
| --- | --- |
| `gemma-4-E2B-it-Q4_K_M.gguf` | 3106738272 |
| `mmproj-gemma-4-E2B-it-Q8_0.gguf` | 557368064 |

`ls -lh` shows about `2.9G` and `532M`. A smaller number is an incomplete download.

Optional text check, before the camera is involved. Quit App Lab first.

```sh
cd /home/arduino/llama.cpp/build/bin
export LD_LIBRARY_PATH="$PWD"
./llama-cli \
  -m /home/arduino/models/gemma-4-E2B-it-Q4_K_M.gguf \
  --no-mmproj \
  -p "Respond with exactly three words confirming you are operational." \
  -n 32 -t 4 -c 512 --temp 0.1 --single-turn
```

The first reply takes about a minute. A log line about failing to fit the model into device memory means the accelerator path was skipped. The process continues on the CPU. Keep the context at 512 for this check. Stop `llama-cli` before the next section so the board can load the model again.

## 5. Prepare the computer

On the computer, from this project directory:

```sh
python3 -m venv .venv
.venv/bin/pip install -r mac/requirements.txt
```

Install the Arduino CLI into `tools/` (that directory is local and is not part of the git history):

```sh
mkdir -p tools
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | BINDIR="$PWD/tools" sh
./tools/arduino-cli version
```

Install the Nano core:

```sh
./tools/arduino-cli core update-index
./tools/arduino-cli core install arduino:mbed_nano
```

The Library Manager copy of `Arduino_OV767X` (0.0.2) cannot start an OV7675. Install the current GitHub copy:

```sh
curl -fsSL -o /tmp/ov767x.zip https://github.com/arduino-libraries/Arduino_OV767X/archive/refs/heads/master.zip
rm -rf "$HOME/Documents/Arduino/libraries/Arduino_OV767X"
unzip -q /tmp/ov767x.zip -d /tmp
mv /tmp/Arduino_OV767X-master "$HOME/Documents/Arduino/libraries/Arduino_OV767X"
```

## 6. Seat the camera hardware

1. Seat the Nano in the TinyML shield's two 1x15 headers with the USB silkscreen lined up. A Nano seated backwards does not run this sketch.
2. Seat the OV7675 in the shield's 2x10 header. The lens is farther from the Nano, the pins are fully in, and the lens cap is off.
3. Plug the Nano into the computer. The green power LED stays on.

No jumper wires run between the Nano and the Uno Q.

## 7. Upload the camera sketch

The sketch in `nano/tricorder_cam` waits for the letter `S` on serial, then sends one QCIF RGB565 frame (176×144). That size fits the Nano. A larger color frame does not.

Find the port:

```sh
./tools/arduino-cli board list
```

On macOS it looks like `/dev/cu.usbmodem…`. This computer used `/dev/cu.usbmodem31201`. Use the port from `board list`.

```sh
./tools/arduino-cli compile --fqbn arduino:mbed_nano:nano33ble nano/tricorder_cam
./tools/arduino-cli upload -p /dev/cu.usbmodem31201 --fqbn arduino:mbed_nano:nano33ble nano/tricorder_cam
```

A warning that the camera library says `mbed` rather than `mbed_nano` can be ignored.

Check the camera on its own, before involving the Uno Q:

```sh
.venv/bin/python mac/relay.py --port /dev/cu.usbmodem31201 --once /tmp/frame.png
```

Open `/tmp/frame.png`. If the colors are swapped, add `--swap-bytes` to this command and to the relay command in the last step.

The relay may say there was no boot banner. That is normal when the sketch is already running. It still takes the next frame. A red LED blinking on the Nano, or the message `CAM_FAIL`, means the camera did not start. Reseat the camera and the Nano, then upload again.

## 8. Copy the viewscreen onto the Uno Q

From this project directory on the computer. Password login as `arduino` is enough.

```sh
ssh arduino@roarduino.local 'mkdir -p ~/tricorder/static'
scp unoq/tricorder.py unoq/start-gemma.sh arduino@roarduino.local:~/tricorder/
scp unoq/static/index.html arduino@roarduino.local:~/tricorder/static/index.html
ssh arduino@roarduino.local 'chmod +x ~/tricorder/start-gemma.sh'
```

`start-gemma.sh` looks for these paths:

| Variable | Default |
| --- | --- |
| `LLAMA_SERVER` | `/home/arduino/llama.cpp/build/bin/llama-server` |
| `MODEL` | `/home/arduino/models/gemma-4-E2B-it-Q4_K_M.gguf` |
| `MMPROJ` | `/home/arduino/models/mmproj-gemma-4-E2B-it-Q8_0.gguf` |

The page sends images to `http://127.0.0.1:8080/v1/chat/completions` on the board. The server listens only on the board, not on the network.

## 9. Run it

Quit App Lab first. You need three sessions.

Session 1, on the Uno Q. Leave it open.

```sh
ssh arduino@roarduino.local
~/tricorder/start-gemma.sh
```

Wait until the log says the server is listening on `http://127.0.0.1:8080`. A line about failing to fit the model into device memory is a warning. The server continues and loads on the CPU.

Session 2, a second SSH login:

```sh
ssh arduino@roarduino.local
python3 ~/tricorder/tricorder.py
```

That prints `tricorder http://0.0.0.0:8090`. The page listens on IPv4 and IPv6.

Session 3, on the computer, from this project directory. Use your Nano port, and add `--swap-bytes` if the test PNG needed it.

```sh
.venv/bin/python mac/relay.py --host http://roarduino.local:8090 --port /dev/cu.usbmodem31201
```

It prints `waiting for Scan on http://roarduino.local:8090`. If the name does not resolve, use the board's address:

```sh
.venv/bin/python mac/relay.py --host http://192.168.1.12:8090 --port /dev/cu.usbmodem31201
```

`hostname -I` on the board shows the current address. Ignore `172.17.0.1`.

## 10. Take a reading

Open `http://roarduino.local:8090` in a browser. If that name fails to load, open `http://<board-ip>:8090`.

Hold the camera a few inches from the subject and press Scan.

The snapshot shows up first. The sentence follows after the board finishes, on the order of a minute. A soft QCIF frame is expected. A working reading is one sentence, for example: "The sensors detect a large, organic, and somewhat amorphous object in the foreground."

## Stop

Close the relay with Ctrl-C. On the board, Ctrl-C the viewscreen and `start-gemma.sh`.

## Where to change things

The report wording lives in the `SYSTEM` string in `unoq/tricorder.py`. The page layout and copy live in `unoq/static/index.html`. After either change, copy that file to the board again with the `scp` commands in step 8.

| What | Where |
| --- | --- |
| Page port | `TRICORDER_PORT` on the board (default `8090`) |
| Model HTTP API | `GEMMA_URL` on the board |
| Model files and `llama-server` | `MODEL`, `MMPROJ`, `LLAMA_SERVER` when starting `start-gemma.sh` |
| Board address the computer calls | `mac/relay.py --host` |
| Swapped red and blue | `mac/relay.py --swap-bytes` |

`tricorder.py` only needs the Python standard library on the Uno Q. The computer needs `pyserial`, from `mac/requirements.txt`.
