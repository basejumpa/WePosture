import time
import json
import os
import RPi.GPIO as GPIO
import matplotlib.pyplot as plt

# ----------------------------
# Pin configuration
# ----------------------------
SCK1 = 6   # clock for first pair
SCK2 = 5   # clock for second pair
DOUT1 = 26
DOUT2 = 19
DOUT3 = 21
DOUT4 = 20

# Offset storage file
OFFSETS_FILE = "hx711_offsets.json"

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(SCK1, GPIO.OUT)
GPIO.setup(SCK2, GPIO.OUT)
GPIO.setup(DOUT1, GPIO.IN)
GPIO.setup(DOUT2, GPIO.IN)
GPIO.setup(DOUT3, GPIO.IN)
GPIO.setup(DOUT4, GPIO.IN)

def read_hx711(dout_pin, sck_pin):
    """Read one value from HX711 on given DOUT and SCK pins"""
    while GPIO.input(dout_pin) == 1:
        time.sleep(0.001)

    count = 0
    for _ in range(24):
        GPIO.output(sck_pin, True)
        count = (count << 1) | GPIO.input(dout_pin)
        GPIO.output(sck_pin, False)

    # Gain = 128 → 1 extra clock pulse
    GPIO.output(sck_pin, True)
    GPIO.output(sck_pin, False)

    if count & 0x800000:  # 24-bit signed
        count -= 1 << 24
    return count

# ----------------------------
# HX711 modules
# ----------------------------
HXs = [
    {"name": "HX1", "dout": DOUT1, "sck": SCK1, "values": []},  # Right Top
    {"name": "HX2", "dout": DOUT2, "sck": SCK1, "values": []},  # Right Bottom
    {"name": "HX3", "dout": DOUT3, "sck": SCK2, "values": []},  # Left Bottom
    {"name": "HX4", "dout": DOUT4, "sck": SCK2, "values": []},  # Left Top
]

# Square geometry
R = 1.0
positions = {
    "HX1": (+R, +R),
    "HX2": (+R, -R),
    "HX3": (-R, -R),
    "HX4": (-R, +R),
}

cog_x, cog_y = [], []


def zero_system():
    """Zero the system and store offsets persistently"""
    offsets = {}
    print("Zeroing... please keep the system unloaded.")
    for hx in HXs:
        vals = []
        for _ in range(50):  # 50 samples per HX711
            vals.append(read_hx711(hx["dout"], hx["sck"]))
        offsets[hx["name"]] = sum(vals) / len(vals)
        print(f"{hx['name']} zero offset = {offsets[hx['name']]:.2f}")

    # Save to file
    with open(OFFSETS_FILE, "w") as f:
        json.dump(offsets, f, indent=2)
    print(f"Offsets saved to {OFFSETS_FILE}")
    return offsets


def load_offsets():
    """Load offsets from file or zero if not present"""
    if os.path.exists(OFFSETS_FILE):
        with open(OFFSETS_FILE, "r") as f:
            offsets = json.load(f)
        print(f"Loaded offsets from {OFFSETS_FILE}: {offsets}")
        return offsets
    else:
        return zero_system()


try:
    # Load or compute offsets
    zero_offsets = load_offsets()

    print("Starting measurements... Press Ctrl+C to stop.")
    for i in range(200):  # take 200 samples
        weights, line = [], f"{i}: "
        for hx in HXs:
            raw = read_hx711(hx["dout"], hx["sck"])
            val = raw - zero_offsets[hx["name"]]  # apply tare
            hx["values"].append(val)
            weights.append((hx["name"], val))
            line += f"{hx['name']}={val:.0f}  "
        print(line)

        # Compute CoG
        sum_w = sum(max(v, 0) for _, v in weights)
        if sum_w > 0:
            x = sum(max(v, 0) * positions[n][0] for n, v in weights) / sum_w
            y = sum(max(v, 0) * positions[n][1] for n, v in weights) / sum_w
            cog_x.append(x)
            cog_y.append(y)
        else:
            cog_x.append(0)
            cog_y.append(0)

        time.sleep(0.05)

    # ----------------------------
    # Plot raw values
    # ----------------------------
    plt.figure(figsize=(10, 5))
    for hx in HXs:
        plt.plot(hx["values"], label=hx["name"])
    plt.title("HX711 Raw Values (zeroed)")
    plt.xlabel("Sample")
    plt.ylabel("ADC Value (relative)")
    plt.legend()
    plt.savefig("hx711_quad_plot.png")
    print("Saved plot as hx711_quad_plot.png")

    # ----------------------------
    # Plot CoG trajectory
    # ----------------------------
    fig, ax = plt.subplots(figsize=(6, 6))
    circle = plt.Circle((0, 0), R, color="lightgray", fill=False)
    ax.add_artist(circle)

    # Draw square
    square_x = [+R, +R, -R, -R, +R]
    square_y = [+R, -R, -R, +R, +R]
    ax.plot(square_x, square_y, "k-")

    # Plot trajectory of CoG
    ax.plot(cog_x, cog_y, "r-", label="Center of Gravity Path")
    ax.plot([cog_x[0]], [cog_y[0]], "go", label="Start")
    ax.plot([cog_x[-1]], [cog_y[-1]], "ro", label="End")

    ax.set_aspect("equal", "box")
    ax.set_xlim(-R * 1.2, R * 1.2)
    ax.set_ylim(-R * 1.2, R * 1.2)
    ax.set_title("Center of Gravity from 4 Load Cells")
    ax.legend()
    plt.savefig("hx711_cog_plot.png")
    print("Saved plot as hx711_cog_plot.png")

except KeyboardInterrupt:
    print("\nStopped by user (Ctrl+C).")
finally:
    GPIO.cleanup()
    print("GPIO cleaned up. Exiting gracefully.")
