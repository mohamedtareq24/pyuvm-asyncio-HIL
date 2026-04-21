# UART Loopback HIL Example

This example runs one UART TX agent on one loopback serial port. The TX agent
sends 16-bit packets through the COM port, the RX monitor collects looped-back
packets, and the scoreboard compares expected vs actual.

Test flow follows the ad-hoc base-test pattern (similar to your ECG HIL
`test_lib.py`): a base test owns common setup/run logic, and subclasses select
behavior via class attributes. No cocotb decorator-based test registration is
used.

## Wiring

Use an FTDI adapter with TX and RX shorted (loopback):

- TX -> RX
- GND -> GND

## Install

From repository root:

```bash
pip install "git+https://github.com/mohamedtareq24/pyuvm-asyncio-HIL@asyncio-hil"
pip install "pyserial-asyncio>=0.6"
```

## Run

From repository root:

```bash
python examples/UARTLoopback_HIL/run_hil.py --port COM5 --baud 115200 --count 16
```

Choose a specific test class:

```bash
python examples/UARTLoopback_HIL/run_hil.py --port COM5 --test UARTLoopbackSmokeTest
```

Available classes:

- `UARTLoopbackSmokeTest`
- `UARTLoopbackShortBurstTest`

Arguments:

- `--port`: serial port (required)
- `--baud`: baud rate (default: 115200)
- `--count`: packets sent by TX agent (default: 16)
- `--test`: test class name from `testbench.py` (default: `UARTLoopbackSmokeTest`)

## Pass Criteria

The scoreboard reports a match for each expected packet and no mismatches.

### Validated smoke run

Example command used successfully:

```bash
python examples/UARTLoopback_HIL/run_hil.py --port COM3 --baud 115200 --count 4 --test UARTLoopbackSmokeTest
```

Example output pattern:

```text
[TEST CONFIG] UARTLoopbackSmokeTest port=COM3 baud=115200 count_per_agent=4 expected_packets=4
[uvm_test_top.env.scoreboard]: Match [0]: 0xA110
...
[uvm_test_top.env.scoreboard]: Match [3]: 0xA113
```

If you see all `Match` lines and the command exits `0`, the loopback path and
scoreboard checks are working.

Each packet is encoded as:

- High byte: source agent ID (`0xA1`)
- Low byte: payload byte
