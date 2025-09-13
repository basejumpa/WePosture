import time
import json
import math
import RPi.GPIO as GPIO
from statistics import mean, stdev
import matplotlib.pyplot as plt

OFFSETS_FILE = "hx711_offsets.json"

# --- Pin mapping ---
HXs = [
    {"name": "HX1", "dout": 19, "sck": 6},   # Top Right
    {"name": "HX2", "dout": 26, "sck": 6},   # Bottom Right
    {"name": "HX3", "dout": 20, "sck": 5},   # Bottom Left
    {"name": "HX4", "dout": 21, "sck": 5},   # Top Left
]

# --- GPIO setup ---
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for hx in HXs:
    GPIO.setup(hx["sck"], GPIO.OUT)
    GPIO.setup(hx["dout"], GPIO.IN)

def read_hx711(dout_pin, sck_pin, timeout=1.0):
    start = time.time()
    while GPIO.input(dout_pin) == 1:
        if time.time() - start > timeout:
            return None
        time.sleep(0.0001)

    count = 0
    for _ in range(24):
        GPIO.output(sck_pin, True)
        count = (count << 1) | GPIO.input(dout_pin)
        GPIO.output(sck_pin, False)

    GPIO.output(sck_pin, True)
    GPIO.output(sck_pin, False)

    if count & 0x800000:
        count -= 1 << 24
    return count

def zero_system(samples=50):
    print("Zeroing... make sure all load cells are unloaded.")
    offsets, thresholds = {}, {}
    for hx in HXs:
        vals = [read_hx711(hx["dout"], hx["sck"]) for _ in range(samples)]
        vals = [v for v in vals if v is not None]
        if vals:
            avg = mean(vals)
            sd = stdev(vals) if len(vals) > 1 else 0
            offsets[hx["name"]] = avg
            thresholds[hx["name"]] = sd * 3
            print(f"{hx['name']}: offset={avg:.2f}, threshold={thresholds[hx['name']]:.2f}")
        else:
            offsets[hx["name"]] = 0
            thresholds[hx["name"]] = 0
            print(f"{hx['name']}: no data (check wiring).")
    with open(OFFSETS_FILE, "w") as f:
        json.dump({"offsets": offsets, "thresholds": thresholds, "scales": {}}, f, indent=2)
    return offsets, thresholds

def load_offsets():
    try:
        with open(OFFSETS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"offsets": {}, "thresholds": {}, "scales": {}}

def calibrate_system(load_kg: float, samples=50):
    data = load_offsets()
    offsets = data.get("offsets", {})
    if not offsets:
        raise RuntimeError("Device not zeroed. Run zero-device first.")

    scales = {}
    print(f"Calibrating with {load_kg} kg total load...")
    for hx in HXs:
        vals = [read_hx711(hx["dout"], hx["sck"]) for _ in range(samples)]
        vals = [v - offsets.get(hx["name"], 0) for v in vals if v is not None]
        avg = mean(vals) if vals else 1
        scales[hx["name"]] = (load_kg / 4.0) / avg
        print(f"{hx['name']}: scale={scales[hx['name']]:.6f} kg/unit")

    data["scales"] = scales
    with open(OFFSETS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return scales

def plot_cog(results, out_prefix="measurement"):
    # --- Geometry setup ---
    r = 1.0
    corner = r / math.sqrt(2)  # √2/2 ≈ 0.707
    positions = {
        "HX1": ( corner,  corner),  # Top Right
        "HX2": ( corner, -corner),  # Bottom Right
        "HX3": (-corner, -corner),  # Bottom Left
        "HX4": (-corner,  corner),  # Top Left
    }

    cog_x, cog_y, total_weights = [], [], []
    for rvals in results:
        weights = [rvals.get(hx, 0) for hx in positions]
        total = sum(weights)
        total_weights.append(total)
        if total == 0:
            continue
        x = sum(w * positions[hx][0] for hx, w in zip(positions, weights)) / total
        y = sum(w * positions[hx][1] for hx, w in zip(positions, weights)) / total
        cog_x.append(x)
        cog_y.append(y)

    # --- Plot ---
    plt.figure(figsize=(6, 6))
    ax = plt.gca()
    # Circle
    circle = plt.Circle((0, 0), r, color="gray", fill=False)
    ax.add_artist(circle)
    # Square
    square = [
        positions["HX1"],
        positions["HX2"],
        positions["HX3"],
        positions["HX4"],
        positions["HX1"],  # close path
    ]
    sx, sy = zip(*square)
    plt.plot(sx, sy, "k--", label="Square")

    # Path of CoG
    plt.plot(cog_x, cog_y, "r.-", label="CoG path")

    # Embed mean total weight as annotation in the plot
    if total_weights:
        scalar_weight = sum(total_weights) / len(total_weights)
        plt.annotate(f"Mean total weight: {scalar_weight:.2f} kg", xy=(0.5, 0.05), xycoords='axes fraction',
                     fontsize=12, color='blue', ha='center', va='center', bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="blue", lw=1))

    plt.title("Center of Gravity Path")
    plt.axis("equal")
    plt.legend()
    cog_file = f"{out_prefix}_cog.png"
    plt.savefig(cog_file)
    plt.close()
    return cog_file


def measure(duration: float, interval=0.1, out_prefix="measurement"):
    """Measure for given duration in seconds and create plots + JSON."""

    data = load_offsets()
    offsets, scales = data.get("offsets", {}), data.get("scales", {})
    if not offsets:
        raise RuntimeError("Device not zeroed. Run zero-device first.")

    results, times = [], []
    t_start = time.time()
    t_end = t_start + duration

    while time.time() < t_end:
        reading = {}
        for hx in HXs:
            raw = read_hx711(hx["dout"], hx["sck"])
            if raw is None:
                continue
            val = raw - offsets.get(hx["name"], 0)
            if hx["name"] in scales and scales[hx["name"]] != 0:
                val *= scales[hx["name"]]
            reading[hx["name"]] = val
        results.append(reading)
        times.append(time.time() - t_start)
        time.sleep(interval)

    # --- Plot 1: Time series ---
    plt.figure(figsize=(10, 6))
    for hx in HXs:
        vals = [r.get(hx["name"], 0) for r in results]
        plt.plot(times, vals, label=hx["name"])
    plt.title("HX711 Measurements Over Time")
    plt.xlabel("Time [s]")
    plt.ylabel("Load (raw or kg)")
    plt.legend()
    ts_file = f"{out_prefix}_timeseries.png"
    plt.savefig(ts_file)
    plt.close()

    # --- Plot 2: CoG path ---
    cog_file = plot_cog(results, out_prefix)

    # --- JSON output ---
    json_file = f"{out_prefix}.json"
    with open(json_file, "w") as f:
        json.dump({
            "measurements": results,
            "times": times,
            "plots": {
                "timeseries": ts_file,
                "cog": cog_file,
            }
        }, f, indent=2)

    print(f"Saved results to {json_file}, {ts_file}, {cog_file}")
    return results, ts_file, cog_file
