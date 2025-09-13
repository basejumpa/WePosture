import time
import RPi.GPIO as GPIO
import matplotlib.pyplot as plt

# Pin configuration
SCK1 = 6   # clock for first pair
SCK2 = 5   # clock for second pair
DOUT1 = 26
DOUT2 = 19
DOUT3 = 21
DOUT4 = 20

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
    # Wait for chip ready (DOUT goes low)
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

    # Convert from 24-bit two's complement
    if count & 0x800000:  
        count -= 1 << 24
    return count

# Define HX711 modules
HXs = [
    {"name": "HX1", "dout": DOUT1, "sck": SCK1, "values": []},
    {"name": "HX2", "dout": DOUT2, "sck": SCK1, "values": []},
    {"name": "HX3", "dout": DOUT3, "sck": SCK2, "values": []},
    {"name": "HX4", "dout": DOUT4, "sck": SCK2, "values": []},
]

try:
    print("Starting 4× HX711 readout... Press Ctrl+C to stop.")
    for i in range(200):  # take 200 samples
        line = f"{i}: "
        for hx in HXs:
            val = read_hx711(hx["dout"], hx["sck"])
            hx["values"].append(val)
            line += f"{hx['name']}={val}  "
        print(line)
        time.sleep(0.05)

    # Plot results
    for hx in HXs:
        plt.plot(hx["values"], label=hx["name"])
    plt.title("HX711 Raw Values")
    plt.xlabel("Sample")
    plt.ylabel("ADC Value")
    plt.legend()
    plt.savefig("hx711_quad_plot.png")
    print("Saved plot as hx711_quad_plot.png")

except KeyboardInterrupt:
    print("\nStopped by user (Ctrl+C).")
finally:
    GPIO.cleanup()
    print("GPIO cleaned up. Exiting gracefully.")
