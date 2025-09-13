import time
import json
import signal
import sys
import RPi.GPIO as GPIO
from statistics import mean, stdev

OFFSETS_FILE = "hx711_offsets.json"

# --- Pin mapping ---
HXs = [
    {"name": "HX1", "dout": 26, "sck": 6},   # Top Right
    {"name": "HX2", "dout": 19, "sck": 6},   # Bottom Right
    {"name": "HX3", "dout": 21, "sck": 5},   # Bottom Left
    {"name": "HX4", "dout": 20, "sck": 5},   # Top Left
]

# --- GPIO setup ---
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for hx in HXs:
    GPIO.setup(hx["sck"], GPIO.OUT)
    GPIO.setup(hx["dout"], GPIO.IN)

def read_hx711(dout_pin, sck_pin, timeout=1.0):
    """Low-level read from one HX711 channel. Returns int or None if timeout."""
    start = time.time()
    while GPIO.input(dout_pin) == 1:
        if time.time() - start > timeout:
            return None  # chip not ready
        time.sleep(0.0001)

    count = 0
    for _ in range(24):
        GPIO.output(sck_pin, True)
        count = (count << 1) | GPIO.input(dout_pin)
        GPIO.output(sck_pin, False)

    # One more clock pulse: Channel A, Gain=128
    GPIO.output(sck_pin, True)
    GPIO.output(sck_pin, False)

    # Convert signed 24-bit
    if count & 0x800000:
        count -= 1 << 24
    return count

def zero_system(samples=50):
    """Collect zero offsets and thresholds for all HX711s (with timeouts)."""
    print("Zeroing... make sure all load cells are unloaded.")

    offsets = {}
    thresholds = {}

    for hx in HXs:
        vals = []
        for _ in range(samples):
            val = read_hx711(hx["dout"], hx["sck"])
            if val is not None:
                vals.append(val)
            time.sleep(0.01)

        if vals:
            avg = mean(vals)
            sd = stdev(vals) if len(vals) > 1 else 0.0
            offsets[hx["name"]] = avg
            thresholds[hx["name"]] = sd * 3
            print(f"{hx['name']}: offset={avg:.2f}, threshold={thresholds[hx['name']]:.2f}")
        else:
            offsets[hx["name"]] = 0
            thresholds[hx["name"]] = 0
            print(f"{hx['name']}: no data (check wiring).")

        # Save progress after each HX
        with open(OFFSETS_FILE, "w") as f:
            json.dump({"offsets": offsets, "thresholds": thresholds}, f, indent=2)

    return offsets, thresholds

def load_or_zero():
    """Try to load offsets; if not present, perform zeroing and save."""
    try:
        with open(OFFSETS_FILE, "r") as f:
            data = json.load(f)
            offsets = data["offsets"]
            thresholds = data["thresholds"]
        print("Loaded stored offsets and thresholds.")
    except (FileNotFoundError, json.JSONDecodeError):
        print("No valid offset file found. Starting zeroing...")
        offsets, thresholds = zero_system()
        print(f"Offsets saved to {OFFSETS_FILE}")
    return offsets, thresholds

def cleanup_and_exit(sig=None, frame=None):
    print("\nCleaning up GPIO and exiting...")
    GPIO.cleanup()
    sys.exit(0)

# Register graceful exit
signal.signal(signal.SIGINT, cleanup_and_exit)
signal.signal(signal.SIGTERM, cleanup_and_exit)

# --- Main ---
if __name__ == "__main__":
    offsets, thresholds = load_or_zero()
    print("Press weights on load cells to see adjusted values (raw - offset).")

    while True:
        readings = {}
        for hx in HXs:
            raw = read_hx711(hx["dout"], hx["sck"])
            if raw is None:
                readings[hx["name"]] = None
            else:
                readings[hx["name"]] = raw - offsets.get(hx["name"], 0)
        print(readings)
        time.sleep(0.2)
