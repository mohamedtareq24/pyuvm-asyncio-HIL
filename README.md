# pyuvm Asyncio Patches — HIL Backend

## Background

pyuvm 4.0.1 is tightly coupled to cocotb. Every internal module imports cocotb
primitives for scheduling, synchronisation, and time reporting. This causes
immediate import failures when no simulator backend is present.

To enable HIL testing against real hardware without a simulator, 7 pyuvm source
files were patched to replace all cocotb primitives with standard `asyncio`
equivalents. The patched library is published at:

```
https://github.com/mohamedtareq24/pyuvm-asyncio-HIL  (branch: asyncio-hil)
```

Install with:

```bash
pip install "git+https://github.com/mohamedtareq24/pyuvm-asyncio-HIL@asyncio-hil"
```

## Installation

### For standalone projects

```bash
pip install "git+https://github.com/mohamedtareq24/pyuvm-asyncio-HIL@asyncio-hil"
pip install "pyserial-asyncio>=0.6"
```

Add this to `requirements.txt` (or your equivalent dependency file):

```txt
git+https://github.com/mohamedtareq24/pyuvm-asyncio-HIL@asyncio-hil
pyserial-asyncio>=0.6
```

### Verify the installed pyuvm source (tutorial)

Use `hil_fork_test/verify_pyuvm_fork.py` to confirm your environment is using
the HIL fork and not a different pyuvm source.

From the repository root:

```bash
python hil_fork_test/verify_pyuvm_fork.py
```

Expected success line:

```text
PASS: pyuvm installed from pyuvm-asyncio-HIL fork
```

Optional: override the expected repository (advanced)

```bash
$env:EXPECTED_PYUVM_REPO = "mohamedtareq24/pyuvm-asyncio-HIL"
python hil_fork_test/verify_pyuvm_fork.py
```

For bash:

```bash
EXPECTED_PYUVM_REPO="mohamedtareq24/pyuvm-asyncio-HIL" python hil_fork_test/verify_pyuvm_fork.py
```

### Transport example for FTDI loopback and HIL

The verification script above checks installation source metadata only. It does
not touch hardware. For UART hardware tests (including FTDI loopback), use the
transport class in `hil_fork_test/hil_serial_transport.py`.

This class provides the methods expected by driver/monitor code:

- `open(port, baud_rate)`
- `write_packet(packet_16b)`
- `read_rx_byte()`
- `close()`

Minimal usage:

```python
import asyncio

from hil_fork_test.hil_serial_transport import HilSerialTransport


async def main() -> None:
    tr = HilSerialTransport()
    await tr.open(port="COM5", baud_rate=115200)
    try:
        await tr.write_packet(0x1234)
        rx = await asyncio.wait_for(tr.read_rx_byte(), timeout=1.0)
        print(f"RX byte: 0x{rx:02X}")
    finally:
        await tr.close()


asyncio.run(main())
```

If TX and RX are looped back correctly on the FTDI adapter, the read path
should return bytes you transmitted.

### Single-agent UART loopback example

For a complete pyuvm HIL testbench with one UART TX agent sending on COM,
an RX monitor collecting looped-back data, and a scoreboard checking matches, see:

`examples/UARTLoopback_HIL/README.md`

### Loopback hardware check (example)

Use this as a quick physical-port sanity check with FTDI TX/RX loopback:

```bash
python examples/UARTLoopback_HIL/run_hil.py --port COM3 --baud 115200 --count 4 --test UARTLoopbackSmokeTest
```

Expected output pattern:

```text
[TEST CONFIG] UARTLoopbackSmokeTest port=COM3 baud=115200 count_per_agent=4 expected_packets=4
[uvm_test_top.env.scoreboard]: Match [0]: 0xA110
[uvm_test_top.env.scoreboard]: Match [1]: 0xA111
[uvm_test_top.env.scoreboard]: Match [2]: 0xA112
[uvm_test_top.env.scoreboard]: Match [3]: 0xA113
```

Pass criteria:

- All scoreboard lines show `Match`
- Process exits with code `0`

Common failures:

- Wrong `--port` value
- FTDI TX/RX loopback wiring missing
- Port already open in another tool

Quick smoke run (validated):

```bash
python examples/UARTLoopback_HIL/run_hil.py --port COM3 --baud 115200 --count 4 --test UARTLoopbackSmokeTest
```

Expected behavior:

```text
[TEST CONFIG] UARTLoopbackSmokeTest port=COM3 baud=115200 count_per_agent=4 expected_packets=4
[uvm_test_top.env.scoreboard]: Match [0]: 0xA110
...
[uvm_test_top.env.scoreboard]: Match [3]: 0xA113
```

If your FTDI loopback is wired correctly, all packet compares should report as
`Match` and the process should exit with code `0`.

---

## Patched Files

### `pyuvm/_utils.py`

**Problem:** Imported cocotb to read its version tuple, crashing without a simulator.

**Fix:** Removed the cocotb import. Hardcoded the version tuple that the rest of
pyuvm expects:

```python
# Before
import cocotb
cocotb_version_info = cocotb.__version_info__

# After
cocotb_version_info = (2, 0, 0)
```

---

### `pyuvm/s05_base_classes.py`

**Problem:** `get_sim_time()` was imported from `cocotb.utils` and called during
object construction.

**Fix:** Replaced with a stub that returns `0`:

```python
# Before
from cocotb.utils import get_sim_time

# After
def get_sim_time(units=None):
    return 0
```

---

### `pyuvm/s06_reporting_classes.py`

**Problem:** `FormatterBase` was set to cocotb's custom log formatter, and
`SimTimeContextFilter` used cocotb's sim-time API.

**Fix:** `FormatterBase` falls back to `logging.Formatter`. `SimTimeContextFilter`
becomes a no-op filter:

```python
# Before
from cocotb.logging import SimTimeContextFilter, SimFormatter as FormatterBase

# After
import logging
FormatterBase = logging.Formatter

class SimTimeContextFilter(logging.Filter):
    def filter(self, record):
        return True
```

---

### `pyuvm/s09_phasing.py`

**Problem:** `cocotb.start_soon()` was used to launch phase coroutines in the
background. Without cocotb there is no scheduler to call it on.

**Fix:** Replaced with `asyncio.get_event_loop().create_task()`:

```python
# Before
import cocotb
cocotb.start_soon(method())

# After
import asyncio
asyncio.get_event_loop().create_task(method())
```

This is the most critical patch — it enables `run_phase()` coroutines in
`UARTTxDriver`, `UARTRxMonitor`, and `ECGScoreboard` to be scheduled and run
concurrently under the asyncio event loop.

---

### `pyuvm/s13_uvm_component.py`

**Problem:** Same formatter/filter imports as `s06_reporting_classes.py` were
duplicated here.

**Fix:** Same patch applied — `FormatterBase = logging.Formatter`, no-op
`SimTimeContextFilter`.

---

### `pyuvm/s14_15_python_sequences.py`

**Problem:** `cocotb.triggers.Event` was imported for sequence handshaking. The
`cocotb.triggers` module itself requires the cocotb C extension and cannot be
imported without a simulator.

**Fix:** Replaced directly with `asyncio.Event`:

```python
# Before
from cocotb.triggers import Event as CocotbEvent

# After
from asyncio import Event as CocotbEvent
```

This enables `start_item()` / `finish_item()` handshaking between sequences and
the driver to work under asyncio.

---

### `pyuvm/utility_classes.py`

**Problem:** `UVMQueue` was built on `cocotb.queue.Queue` and `cocotb.triggers.Event`.
`NullTrigger` used a cocotb trigger to yield one scheduler tick.

**Fix:** Full rewrite on asyncio primitives:

```python
# Before
import cocotb.queue
import cocotb.triggers
queue = cocotb.queue.Queue()
event = cocotb.triggers.Event()
await NullTrigger()

# After
import asyncio
queue = asyncio.Queue()
event = asyncio.Event()
await asyncio.sleep(0)
```

`UVMQueue.get()` and `UVMQueue.put()` now delegate to `asyncio.Queue`.
`UVMQueue.get_nowait()` raises `asyncio.QueueEmpty` on empty, which pyuvm's
TLM FIFOs already handle correctly.

---

## How the Driver Works After Patches

`UARTTxDriver.run_phase()` is an `async def` coroutine that loops forever,
pulling sequence items and writing them to the UART transport:

```python
async def run_phase(self):
    while True:
        tr = await self.seq_item_port.get_next_item()
        for packet, _, _ in tr.iter_packet_bytes():
            await asyncio.wait_for(
                self.transport.write_packet(packet),
                timeout=self.cfg.byte_timeout_s,
            )
        self.seq_item_port.item_done()
        self.ap.write(tr)
```

The patch to `s09_phasing.py` (`create_task` instead of `start_soon`) is what
causes this coroutine to be scheduled and run concurrently with the scoreboard
and monitor under the asyncio event loop.

---

## How the Monitor Works After Patches

`UARTRxMonitor.run_phase()` loops forever reading bytes from the physical UART:

```python
async def run_phase(self):
    while True:
        data = await asyncio.wait_for(
            self.transport.read_rx_byte(),
            timeout=self.cfg.byte_timeout_s,
        )
        item = UARTRxSeqItem(f"rx_item_{seq_id}", rx_byte=data & 0xFF)
        self.ap.write(item)
```

The monitor publishes each received byte as a `UARTRxSeqItem` to its analysis
port, which feeds the scoreboard's `dut_tx_fifo`. This works without any cocotb
change because `uvm_analysis_port.write()` is synchronous, and the asyncio
event loop drives the `await` calls.

---

## How Tests Work After Patches

Tests extend `uvm_test` and define `SEQ_CLASS` and `EXPECTED_EPOCHS`:

```python
class ECGSmokeTest(ECGBaseTest):
    SEQ_CLASS = ECGOneEpochSequence
    EXPECTED_EPOCHS = 1
```

The entry point in `run_hil.py` launches the test with:

```python
async def _main():
    args = _parse_args()
    _configure_env(args)
    await uvm_root().run_test(args.test)

asyncio.run(_main())
```

`uvm_root().run_test()` drives the UVM phase machine, which calls
`build_phase → connect_phase → run_phase` on all components. The `run_phase`
coroutines (driver, monitor, scoreboard tasks) are all scheduled via
`asyncio.get_event_loop().create_task()` (the patched `start_soon`), and run
concurrently under the single `asyncio.run()` event loop. No cocotb, no
simulator.

---