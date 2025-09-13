import time
import json
import signal
import sys
import RPi.GPIO as GPIO
from statistics import mean, stdev
import matplotlib.pyplot as plt

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
    print("Measuring 200 samples for plots...")

    values = {hx["name"]: [] for hx in HXs}
    cog_path = []

    for i in range(200):  # take 200 samples
        readings = {}
        for hx in HXs:
            raw = read_hx711(hx["dout"], hx["sck"])
            if raw is None:
                readings[hx["name"]] = None
            else:
                readings[hx["name"]] = raw - offsets.get(hx["name"], 0)
                values[hx["name"]].append(readings[hx["name"]])
        # --- compute center of gravity if all four values valid ---
        if all(readings[hx["name"]] is not None for hx in HXs):
            # map to square corners
            weights = [
                ("HX1", (1, 1)),   # Top Right
                ("HX2", (1, -1)),  # Bottom Right
                ("HX3", (-1, -1)), # Bottom Left
                ("HX4", (-1, 1)),  # Top Left
            ]
            sum_w = sum(abs(readings[name]) for name, _ in weights)
            if sum_w > 0:
                cx = sum(readings[name] * pos[0] for name, pos in weights) / sum_w
                cy = sum(readings[name] * pos[1] for name, pos in weights) / sum_w
                cog_path.append((cx, cy))
        time.sleep(0.05)

    # --- Plot 1: Time series ---
    plt.figure()
    for name, vals in values.items():
        plt.plot(vals, label=name)
    plt.title("HX711 Raw Values (offset corrected)")
    plt.xlabel("Sample")
    plt.ylabel("ADC Value")
    plt.legend()
    plt.savefig("hx711_timeseries.png")
    print("Saved hx711_timeseries.png")

    # --- Plot 2: Square-in-circle with COG path ---
    fig, ax = plt.subplots()
    circle = plt.Circle((0, 0), 1.0, color="lightgray", fill=False)
    ax.add_artist(circle)
    square_x = [1, 1, -1, -1, 1]
    square_y = [1, -1, -1, 1, 1]
    ax.plot(square_x, square_y, "k-")
    if cog_path:
        xs, ys = zip(*cog_path)
        ax.plot(xs, ys, "r-", label="COG path")
        ax.plot(xs[-1], ys[-1], "ro", label="Last COG")
    ax.set_aspect("equal", "box")
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-1.2, 1.2)
    ax.set_title("Center of Gravity Path")
    ax.legend()
    plt.savefig("hx711_cog.png")
    print("Saved hx711_cog.png")

    cleanup_and_exit()
