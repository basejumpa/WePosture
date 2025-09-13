# WeBalance

**WIP - Work In Progress**

Just applied some minor modifications to the example in Getting Started at  https://pypi.org/project/hx711-multi/

```bash
poetry install
poetry run python -m webalance
```


- HX1 is Right Top. Weight is positive
- HX2 is Right Bottom. Weight is positive
- HX3 is Left Bottom. Weight is positive
- HX4 is Left Top. Weight is positive

```bash
poetry run python -m webalance zero-device
poetry run python -m webalance calibrate-device 20.0
poetry run python -m webalance measure 10.0
```
