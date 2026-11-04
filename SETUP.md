# Set up the tricorder from scratch

Point the TinyML-kit camera at something, press Scan, and Gemma 4 E2B on an Arduino Uno Q writes a one-line report. The computer only carries the camera frame over USB. The page and the model both run on the Uno Q.

Nothing is wired between the Nano and the Uno Q.

```
OV7675  →  Nano 33 BLE  →  USB serial  →  computer (relay.py)
                                              │
                                              ▼
                         browser  ←  Uno Q (tricorder.py + Gemma)
```

Build `llama.cpp` and download the Gemma text weights by following [GEMMA_SETUP.md](GEMMA_SETUP.md) first. This guide does not repeat those steps. It adds the vision projector, the camera sketch, and the viewscreen.

Quit Arduino App Lab before you start Gemma here. The model needs the board's memory. Also stop the chat server from GEMMA_SETUP.md if it is still running (Ctrl-C in that Arduino terminal). It uses port 8080, and `start-gemma.sh` needs that same port.

## Two terminals

You switch between two shells. Each command below says which one.

**Computer terminal.** A normal terminal on your Mac or PC. You are not logged into the board. The prompt is your own account, for example `you@your-mac ~ %`. Relative paths such as `mac/relay.py`, `nano/tricorder_cam`, `unoq/`, `.venv`, and `./tools` only work after you `cd` into this project directory.

**Arduino terminal.** An SSH session on the Uno Q. You open it from the computer terminal with `ssh`, and from then on that window runs on the board. The prompt looks like `arduino@YOUR_BOARD_NAME:~$`. A path that starts with `~/` or `/home/arduino/` in this window is on the board, not on your computer. The `>_` button at the bottom left of Arduino App Lab is also an Arduino terminal.

## Replace these before you run a command

These tokens are not real values. Type your own in their place. Leave every other part of the command as written.

| Token | Replace with | Example from one setup |
| --- | --- | --- |
| `PROJECT_DIR` | The folder on your computer that contains `SETUP.md`, `mac/`, `nano/`, and `unoq/` | `/Users/you/Desktop/Arduino-Image-Scanner` |
| `YOUR_BOARD` | The Uno Q's mDNS name or, if the name does not resolve, its Wi-Fi address | `roarduino.local` or `192.168.1.12` |
| `YOUR_NANO_PORT` | The Nano's serial port from `./tools/arduino-cli board list` | `/dev/cu.usbmodem31201` on macOS |

Do not change these unless you deliberately installed something somewhere else:

- `arduino@` is the Linux user App Lab created on the board. The SSH password is the one you set in App Lab.
- `/home/arduino/...` paths are on the board. `~` in an Arduino terminal is `/home/arduino`.
- `arduino:mbed_nano:nano33ble` is the board type for the Nano 33 BLE.
- `$HOME` in a computer-terminal command expands to your computer account's home folder (on macOS, `/Users/yourname`). Do not replace it with the board user.

## Where files are saved

| File | Machine | Saved at |
| --- | --- | --- |
| Python virtualenv | Computer | `PROJECT_DIR/.venv/` |
| Arduino CLI | Computer | `PROJECT_DIR/tools/arduino-cli` |
| OV767X library | Computer | `$HOME/Documents/Arduino/libraries/Arduino_OV767X/` |
| One-shot camera test image | Computer | `/tmp/frame.png` |
| Gemma text weights and `llama-server` | Uno Q | Already placed by [GEMMA_SETUP.md](GEMMA_SETUP.md): `/home/arduino/models/gemma-4-E2B-it-Q4_K_M.gguf` and `/home/arduino/llama.cpp/build/bin/llama-server` |
| Vision projector | Uno Q | `/home/arduino/models/mmproj-gemma-4-E2B-it-Q8_0.gguf` |
| Viewscreen program and launcher | Uno Q | `/home/arduino/tricorder/tricorder.py` and `/home/arduino/tricorder/start-gemma.sh` |
| Web page | Uno Q | `/home/arduino/tricorder/static/index.html` |

`scp` is typed in the computer terminal. It reads a file from `PROJECT_DIR` and writes it to the path after the colon, which is on the board.

## What you need

- Arduino Uno Q, a USB-C cable, and Arduino App Lab on the computer
- Arduino Nano 33 BLE seated in the TinyML shield
- OV7675 camera in the shield's camera header
- A computer on the same Wi-Fi network, with Python 3 and a USB port for the Nano
- This project directory (`PROJECT_DIR`)
- The Gemma install from [GEMMA_SETUP.md](GEMMA_SETUP.md) already finished on the board

## 1. Prepare the Uno Q

Install Arduino App Lab and connect the Uno Q over USB. Walk through the first-time prompts:

1. Give the board a name. One setup used `RoArduino`, which then answered as `roarduino.local`. Your name becomes the `YOUR_BOARD` hostname (`that-name.local`).
2. Join the same Wi-Fi network as the computer.
3. Set a Linux password for the user `arduino`. That password is the SSH password.
4. Leave SSH enabled. App Lab turns it on as part of this setup.

**Computer terminal.** This command opens an Arduino terminal. Replace `YOUR_BOARD` with the name from step 1 plus `.local`:

```sh
ssh arduino@YOUR_BOARD
```

You are done when the prompt changes to the board, for example `arduino@RoArduino:~$`. Later steps that say "Arduino terminal" mean this window, or another window you opened the same way.

If the name does not resolve, read the board's address from an Arduino terminal (the App Lab `>_` shell works). Ignore `172.17.0.1`. That address is a local bridge on the board, not its Wi-Fi address.

```sh
hostname -I
```

Use the other address as `YOUR_BOARD` (no `.local`), still from the computer terminal:

```sh
ssh arduino@YOUR_BOARD
```

## 2. Add the vision projector

[GEMMA_SETUP.md](GEMMA_SETUP.md) downloads the text weights only. This project also needs the vision projector, or Scan has nothing to look at.

**Arduino terminal.** The file is saved on the board at `/home/arduino/models/mmproj-gemma-4-E2B-it-Q8_0.gguf`. Nothing in this command is a placeholder. `-C -` resumes a partial file if Wi-Fi drops. Run it again until the size matches.

```sh
mkdir -p /home/arduino/models
cd /home/arduino/models
curl -L -C - -o mmproj-gemma-4-E2B-it-Q8_0.gguf \
  https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF/resolve/main/mmproj-gemma-4-E2B-it-Q8_0.gguf
```

A finished projector is 557368064 bytes (`ls -lh` shows about `532M`). A smaller number is an incomplete download.

```sh
stat -c '%n %s' /home/arduino/models/mmproj-gemma-4-E2B-it-Q8_0.gguf
```

`start-gemma.sh` expects these three paths, which match GEMMA_SETUP.md plus the file you just saved:

| Variable | Path on the Uno Q |
| --- | --- |
| `LLAMA_SERVER` | `/home/arduino/llama.cpp/build/bin/llama-server` |
| `MODEL` | `/home/arduino/models/gemma-4-E2B-it-Q4_K_M.gguf` |
| `MMPROJ` | `/home/arduino/models/mmproj-gemma-4-E2B-it-Q8_0.gguf` |

## 3. Prepare the computer

**Computer terminal.** `cd` into the project first. Replace `PROJECT_DIR`.

```sh
cd PROJECT_DIR
```

The virtualenv is created at `PROJECT_DIR/.venv/` on the computer. Scripts inside it store that folder's full path. If the project was renamed or moved, or if `.venv` is already there, delete it first. Running `python3 -m venv .venv` again on an existing folder leaves the old path in place, and `pip` then fails with `bad interpreter: No such file or directory`.

```sh
rm -rf .venv
python3 -m venv .venv
.venv/bin/pip install -r mac/requirements.txt
```

If the prompt already shows `(.venv)`, run `deactivate` after the new environment is created. This guide calls `.venv/bin/pip` and `.venv/bin/python` by path, so you do not have to activate it.

The Arduino CLI is saved at `PROJECT_DIR/tools/arduino-cli`. `tools/` stays on your computer and is not part of the git history.

```sh
mkdir -p tools
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | BINDIR="$PWD/tools" sh
./tools/arduino-cli version
```

Install the Nano core. Still the computer terminal, still `PROJECT_DIR`:

```sh
./tools/arduino-cli core update-index
./tools/arduino-cli core install arduino:mbed_nano
```

The Library Manager copy of `Arduino_OV767X` (0.0.2) cannot start an OV7675. Install the current GitHub copy. It is saved on the computer at `$HOME/Documents/Arduino/libraries/Arduino_OV767X/`. `$HOME` is your computer account, not `arduino`. If Arduino uses a different sketchbook folder, replace `$HOME/Documents/Arduino/libraries` with that folder (Arduino IDE: Settings → Sketchbook location, then `libraries` inside it).

```sh
curl -fsSL -o /tmp/ov767x.zip https://github.com/arduino-libraries/Arduino_OV767X/archive/refs/heads/master.zip
rm -rf "$HOME/Documents/Arduino/libraries/Arduino_OV767X"
unzip -q /tmp/ov767x.zip -d /tmp
mv /tmp/Arduino_OV767X-master "$HOME/Documents/Arduino/libraries/Arduino_OV767X"
```

The zip itself is only a temp file at `/tmp/ov767x.zip` on the computer.

## 4. Seat the camera hardware

1. Seat the Nano in the TinyML shield's two 1x15 headers with the USB silkscreen lined up. A Nano seated backwards does not run this sketch.
2. Seat the OV7675 in the shield's 2x10 header. The lens is farther from the Nano, the pins are fully in, and the lens cap is off.
3. Plug the Nano into the computer. The green power LED stays on.

No jumper wires run between the Nano and the Uno Q.

## 5. Upload the camera sketch

The sketch in `PROJECT_DIR/nano/tricorder_cam` waits for the letter `S` on serial, then sends one QCIF RGB565 frame (176×144). That size fits the Nano. A larger color frame does not.

**Computer terminal**, in `PROJECT_DIR`. Find the port:

```sh
./tools/arduino-cli board list
```

On macOS the Nano looks like `/dev/cu.usbmodem…`. Copy that whole path. It is `YOUR_NANO_PORT` in the next commands. One computer used `/dev/cu.usbmodem31201`. Yours will differ. Do not change `--fqbn arduino:mbed_nano:nano33ble` or the sketch folder `nano/tricorder_cam`.

```sh
./tools/arduino-cli compile --fqbn arduino:mbed_nano:nano33ble nano/tricorder_cam
./tools/arduino-cli upload -p YOUR_NANO_PORT --fqbn arduino:mbed_nano:nano33ble nano/tricorder_cam
```

A warning that the camera library says `mbed` rather than `mbed_nano` can be ignored.

Check the camera on its own, before involving the Uno Q. The PNG is saved on the computer at `/tmp/frame.png`. Replace `YOUR_NANO_PORT` only.

```sh
.venv/bin/python mac/relay.py --port YOUR_NANO_PORT --once /tmp/frame.png
```

Open `/tmp/frame.png` from the computer (Finder → Go → Go to Folder, or `open /tmp/frame.png` in the computer terminal). If the colors are swapped, add `--swap-bytes` to this command and to the relay command in the last step.

The relay may say there was no boot banner. That is normal when the sketch is already running. It still takes the next frame. A red LED blinking on the Nano, or the message `CAM_FAIL`, means the camera did not start. Reseat the camera and the Nano, then upload again.

## 6. Copy the viewscreen onto the Uno Q

**Computer terminal**, in `PROJECT_DIR`. These commands read files from `PROJECT_DIR/unoq/` on the computer and write them on the board. Replace `YOUR_BOARD` in every line. Leave `~/tricorder` as written: on the board that is `/home/arduino/tricorder/`.

```sh
ssh arduino@YOUR_BOARD 'mkdir -p ~/tricorder/static'
scp unoq/tricorder.py unoq/start-gemma.sh arduino@YOUR_BOARD:~/tricorder/
scp unoq/static/index.html arduino@YOUR_BOARD:~/tricorder/static/index.html
ssh arduino@YOUR_BOARD 'chmod +x ~/tricorder/start-gemma.sh'
```

After this, the board has:

- `/home/arduino/tricorder/tricorder.py`
- `/home/arduino/tricorder/start-gemma.sh`
- `/home/arduino/tricorder/static/index.html`

The page sends images to `http://127.0.0.1:8080/v1/chat/completions` on the board. That server listens only on the board, not on the network.

## 7. Run it

Quit App Lab first. Stop the GEMMA_SETUP.md chat server if it is still running. You need three terminals at once. Leave each one open.

**Arduino terminal 1.** From a computer terminal, SSH in, then run the launcher on the board. Replace `YOUR_BOARD`. The second line runs only after the prompt is on the board.

```sh
ssh arduino@YOUR_BOARD
~/tricorder/start-gemma.sh
```

`~/tricorder/start-gemma.sh` is `/home/arduino/tricorder/start-gemma.sh`. Wait until the log says the server is listening on `http://127.0.0.1:8080`. A line about failing to fit the model into device memory is a warning. The server continues and loads on the CPU.

**Arduino terminal 2.** Open a second computer terminal and SSH in again. Do not type this in terminal 1.

```sh
ssh arduino@YOUR_BOARD
python3 ~/tricorder/tricorder.py
```

`tricorder.py` is the copy at `/home/arduino/tricorder/tricorder.py`. That prints `tricorder http://0.0.0.0:8090`. The page listens on IPv4 and IPv6.

**Computer terminal.** A third window, not an SSH session. `cd` to `PROJECT_DIR`. Replace `YOUR_BOARD` and `YOUR_NANO_PORT`. Add `--swap-bytes` after the port only if `/tmp/frame.png` had swapped colors.

```sh
cd PROJECT_DIR
.venv/bin/python mac/relay.py --host http://YOUR_BOARD:8090 --port YOUR_NANO_PORT
```

It prints `waiting for Scan on http://YOUR_BOARD:8090`. If you used an mDNS name and it does not resolve, run `hostname -I` in an Arduino terminal, ignore `172.17.0.1`, and run the same command again with that address as `YOUR_BOARD`.

## 8. Take a reading

On the computer, open a browser to `http://YOUR_BOARD:8090`. Same host you used for `--host`, without the `:8090` mismatch: if the relay uses an IP, the browser must use that IP too.

Hold the camera a few inches from the subject and press Scan.

The snapshot shows up first. The sentence follows after the board finishes, on the order of a minute. A soft QCIF frame is expected. A working reading is one sentence, for example: "The sensors detect a large, organic, and somewhat amorphous object in the foreground."

## Stop

In the computer terminal that is running the relay, press Ctrl-C.

In Arduino terminal 2, press Ctrl-C to stop the viewscreen.

In Arduino terminal 1, press Ctrl-C to stop `start-gemma.sh`.

## Where to change things

The report wording lives in the `SYSTEM` string in `PROJECT_DIR/unoq/tricorder.py` on the computer. The page layout and copy live in `PROJECT_DIR/unoq/static/index.html`. Editing those files on the computer does nothing until you copy them again with the `scp` commands in step 6. Those commands overwrite `/home/arduino/tricorder/tricorder.py` and `/home/arduino/tricorder/static/index.html` on the board.

| What | Where |
| --- | --- |
| Page port | `TRICORDER_PORT` in the Arduino terminal that starts `tricorder.py` (default `8090`) |
| Model HTTP API | `GEMMA_URL` in that same Arduino terminal |
| Model files and `llama-server` | `MODEL`, `MMPROJ`, `LLAMA_SERVER` in the Arduino terminal that starts `start-gemma.sh`, if your copies are not in `/home/arduino/models` and `/home/arduino/llama.cpp/build/bin` |
| Board address the computer calls | `YOUR_BOARD` in `mac/relay.py --host` and in the browser URL |
| Nano serial port | `YOUR_NANO_PORT` |
| Swapped red and blue | `--swap-bytes` on the computer-terminal relay command |

`tricorder.py` only needs the Python standard library on the Uno Q. The computer needs `pyserial`, from `mac/requirements.txt`, installed into `PROJECT_DIR/.venv`.
