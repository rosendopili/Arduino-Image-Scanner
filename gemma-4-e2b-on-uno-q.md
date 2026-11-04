# Gemma 4 E2B chat on the Arduino Uno Q

The 512 parameter is the context window (`-c 512`) used with the 4-bit weights `gemma-4-E2B-it-Q4_K_M.gguf`.

These commands install the build tools, compile both binaries, download the weights onto the 18 GB home partition, and open the browser chat. The root partition is only about 5 GB. The home partition is `/home/arduino` on `/dev/mmcblk0p69`.

Quit Arduino App Lab before you load the model. The board has about 3.6 GiB of RAM and no swap.

## 1. Install build tools

Update the package lists and install the compiler dependencies onto the root partition:

```sh
sudo apt update
sudo apt install -y git build-essential cmake curl
```

If the blue "Daemons using outdated libraries" screen appears, press Tab to highlight `<Ok>` at the bottom, then press Enter.

Clean cached `.deb` files so the 5 GB root partition stays free:

```sh
sudo apt clean
```

## 2. Clone and compile llama.cpp

Run this from `/home/arduino` so the build lands on the 18 GB home partition. Build `llama-cli` and `llama-server` in the same command. Building only one of them is what produced "No such file or directory" when the other tool was missing.

```sh
cd /home/arduino
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
cmake -B build
cmake --build build --config Release -j4 --target llama-cli llama-server
```

`ggerganov/llama.cpp` redirects to `ggml-org/llama.cpp`. Leave the compile running until it finishes.

## 3. Download the 4-bit Gemma weights

```sh
mkdir -p /home/arduino/models
curl -L -o /home/arduino/models/gemma-4-E2B-it-Q4_K_M.gguf \
  https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-Q4_K_M.gguf
```

A finished file is about 3.1 GB (3,106,738,272 bytes). Confirm the size and that `/home/arduino` still has free space:

```sh
ls -lh /home/arduino/models/gemma-4-E2B-it-Q4_K_M.gguf
df -h /home/arduino
```

## 4. Read the board's address

```sh
hostname -I | awk '{print $1}'
```

Save that address, for example `192.168.1.45`.

## 5. Start the web chat with a 512 context window

```sh
cd /home/arduino/llama.cpp/build/bin

./llama-server \
  -m /home/arduino/models/gemma-4-E2B-it-Q4_K_M.gguf \
  --host 0.0.0.0 \
  --port 8080 \
  -c 512 \
  -n 128 \
  -t 4 \
  --temp 0.1 \
  --repeat-penalty 1.15
```

`-c 512` keeps the context buffer small so the model fits in RAM and prompt evaluation stays shorter. `-n 128` stops a reply at 128 tokens.

Wait until the console prints that the HTTP server is listening on `0.0.0.0` port `8080`. Leave this terminal open.

A line about failing to fit the model into device memory means the accelerator path was skipped. The server continues on the CPU.

## 6. Open the chat

On a computer, phone, or tablet on the same network, open:

```
http://<YOUR_ARDUINO_IP>:8080
```

`--host 0.0.0.0` accepts connections from other machines on the network.

Because `-c 512` is a compact buffer, the page reports "Context Size Exceeded (545 tokens > 512)" once chat history piles up. Click the reset (trash can) icon before a new question, or after every two or three short exchanges, so the accumulated tokens are cleared.

For short replies, open Settings (the gear icon) and set this system prompt:

```
Answer directly in 1 to 2 sentences without pleasantries.
```

Type a prompt, for example "Why is the sky blue?", and press Send. The reply streams from the Uno Q.
