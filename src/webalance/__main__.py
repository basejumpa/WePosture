import typer
from webalance import hx711_driver

app = typer.Typer(help="HX711 load cell CLI")

@app.command("zero-device")
def zero_device():
    hx711_driver.zero_system()

@app.command("calibrate-device")
def calibrate_device(load_kg: float):
    hx711_driver.calibrate_system(load_kg)

@app.command("measure")
def measure(duration: float):
    hx711_driver.measure(duration)

if __name__ == "__main__":
    app()
