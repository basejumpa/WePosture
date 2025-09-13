import time
import RPi.GPIO as GPIO
import matplotlib.pyplot as plt

# Pin configuration
SCK = 6
DOUT1 = 26
DOUT2 = 19

GPIO.setmode(GPIO.BCM)
GPIO.setup(SCK, GPIO.OUT)
GPIO.setup(DOUT1, GPIO.IN)
GPIO.setup(DOUT2, GPIO.IN)

def read_hx711(dout_pin):
    # Wait for chip ready (DOUT goes low)
    while GPIO.input(dout_pin) == 1:
        time.sleep(0.001)

    count = 0
    for _ in range(24):
        GPIO.output(SCK, True)
        count = (count << 1) | GPIO.input(dout_pin)
        GPIO.output(SCK, False)

    # Gain = 128 → 1 extra clock pulse
    GPIO.output(SCK, True)
    GPIO.output(SCK, False)

    if count & 0x800000:  # negative number
        count -= 1 << 24
    return count

values1 = []
values2 = []

try:
    for i in range(200):  # take 200 samples
        val1 = read_hx711(DOUT1)
        val2 = read_hx711(DOUT2)
        values1.append(val1)
        values2.append(val2)
        print(f"{i}: HX1={val1}, HX2={val2}")
        time.sleep(0.05)

    # Plot both traces
    plt.plot(values1, label="HX711 #1 (DOUT 26)")
    plt.plot(values2, label="HX711 #2 (DOUT 19)")
    plt.title("HX711 Raw Values")
    plt.xlabel("Sample")
    plt.ylabel("ADC Value")
    plt.legend()
    plt.savefig("hx711_dual_plot.png")
    print("Saved plot as hx711_dual_plot.png")

except KeyboardInterrupt:
    print("Stopped by user.")
finally:
    GPIO.cleanup()
