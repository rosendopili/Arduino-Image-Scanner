// One QCIF color frame from the TinyML kit OV7675 when the relay sends "S".
// QCIF RGB565 is 176 x 144 x 2 = 50688 bytes, which fits this board.
// QVGA color does not leave enough SRAM.

#include <Arduino_OV767X.h>

static const uint32_t FRAME_BYTES = 176UL * 144UL * 2UL;
static uint8_t frame[FRAME_BYTES];

static void ledsOff() {
  digitalWrite(LEDR, HIGH);
  digitalWrite(LEDG, HIGH);
  digitalWrite(LEDB, HIGH);
}

static void blinkRedForever() {
  while (true) {
    digitalWrite(LEDR, LOW);
    delay(180);
    digitalWrite(LEDR, HIGH);
    delay(180);
  }
}

static void drainLine() {
  unsigned long start = millis();
  while (millis() - start < 80) {
    if (Serial.available()) {
      if (Serial.read() == '\n') {
        return;
      }
    }
  }
}

void setup() {
  pinMode(LEDR, OUTPUT);
  pinMode(LEDG, OUTPUT);
  pinMode(LEDB, OUTPUT);
  ledsOff();

  Serial.begin(115200);
  unsigned long start = millis();
  while (!Serial && millis() - start < 3000) {
    delay(10);
  }
  Serial.println("BOOT");

  if (!Camera.begin(QCIF, RGB565, 1)) {
    Serial.println("CAM_FAIL");
    blinkRedForever();
  }

  uint32_t need = (uint32_t)Camera.width() * (uint32_t)Camera.height() *
                  (uint32_t)Camera.bytesPerPixel();
  if (need != FRAME_BYTES || Camera.bytesPerPixel() != 2) {
    Serial.println("CAM_SIZE");
    blinkRedForever();
  }

  Serial.println("TRICORDER_CAM");
}

void loop() {
  if (!Serial.available()) {
    return;
  }
  char c = Serial.read();
  if (c != 'S' && c != 's') {
    return;
  }
  drainLine();

  digitalWrite(LEDG, LOW);
  Camera.readFrame(frame);
  Serial.print("FRAME ");
  Serial.print(Camera.width());
  Serial.print(' ');
  Serial.println(Camera.height());
  Serial.write(frame, FRAME_BYTES);
  Serial.print("\nEND\n");
  Serial.flush();
  digitalWrite(LEDG, HIGH);
}
