from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from pyuvm import *

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hil_fork_test.hil_serial_transport import HilSerialTransport


class LoopbackSeqItem(uvm_sequence_item):
    def __init__(self, name: str, source_id: int, payload: int):
        super().__init__(name)
        self.source_id = source_id & 0xFF
        self.payload = payload & 0xFF

    @property
    def packet_16b(self) -> int:
        return ((self.source_id & 0xFF) << 8) | (self.payload & 0xFF)


class ByteBurstSequence(uvm_sequence):
    def __init__(self, name: str, source_id: int, count: int, start_payload: int):
        super().__init__(name)
        self.source_id = source_id
        self.count = count
        self.start_payload = start_payload

    async def body(self):
        for offset in range(self.count):
            payload = (self.start_payload + offset) & 0xFF
            item = LoopbackSeqItem(
                f"item_{self.source_id}_{offset}",
                source_id=self.source_id,
                payload=payload,
            )
            await self.start_item(item)
            await self.finish_item(item)


class Agent0Sequence(ByteBurstSequence):
    def __init__(self, name: str):
        count = ConfigDB().get(None, "", "COUNT_PER_AGENT")
        super().__init__(name, source_id=0xA1, count=count, start_payload=0x10)


class UARTTxDriver(uvm_driver):
    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)

    def start_of_simulation_phase(self):
        self.transport: HilSerialTransport = ConfigDB().get(self, "", "TRANSPORT")
        self.send_lock: asyncio.Lock = ConfigDB().get(self, "", "SEND_LOCK")

    async def run_phase(self):
        while True:
            tr = await self.seq_item_port.get_next_item()
            async with self.send_lock:
                await self.transport.write_packet(tr.packet_16b)
            self.ap.write(tr.packet_16b)
            self.seq_item_port.item_done()


class UARTRxMonitor(uvm_component):
    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)

    def start_of_simulation_phase(self):
        self.transport: HilSerialTransport = ConfigDB().get(self, "", "TRANSPORT")

    async def run_phase(self):
        while True:
            try:
                low_byte = await self.transport.read_rx_byte()
                high_byte = await self.transport.read_rx_byte()
            except RuntimeError as exc:
                # Normal during shutdown after transport.close().
                if "EOF" in str(exc) or "not available" in str(exc):
                    return
                raise
            packet_16b = ((high_byte & 0xFF) << 8) | (low_byte & 0xFF)
            self.ap.write(packet_16b)


class LoopbackScoreboard(uvm_component):
    def build_phase(self):
        self.expected_fifo = uvm_tlm_analysis_fifo("expected_fifo", self)
        self.actual_fifo = uvm_tlm_analysis_fifo("actual_fifo", self)
        self.expected_export = self.expected_fifo.analysis_export
        self.actual_export = self.actual_fifo.analysis_export
        self.expected_get_port = uvm_get_port("expected_get_port", self)
        self.actual_get_port = uvm_get_port("actual_get_port", self)
        self.done_event = asyncio.Event()
        self.passed = True

    def connect_phase(self):
        self.expected_get_port.connect(self.expected_fifo.get_export)
        self.actual_get_port.connect(self.actual_fifo.get_export)

    async def run_phase(self):
        expected_packets = ConfigDB().get(self, "", "EXPECTED_PACKETS")
        for idx in range(expected_packets):
            expected = await self.expected_get_port.get()
            actual = await self.actual_get_port.get()
            if expected != actual:
                self.passed = False
                self.logger.error(
                    f"Mismatch [{idx}]: expected 0x{expected:04X} got 0x{actual:04X}"
                )
            else:
                self.logger.info(f"Match [{idx}]: 0x{actual:04X}")
        self.done_event.set()

    async def wait_done(self, timeout_s: float) -> None:
        await asyncio.wait_for(self.done_event.wait(), timeout=timeout_s)

    def check_phase(self):
        assert self.passed, "Loopback scoreboard detected mismatches"


class UARTTxAgent(uvm_agent):
    def build_phase(self):
        self.seqr = uvm_sequencer("seqr", self)
        self.driver = UARTTxDriver("driver", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.seqr.seq_item_export)


class UARTLoopbackEnv(uvm_env):
    def build_phase(self):
        self.transport = HilSerialTransport()
        self.send_lock = asyncio.Lock()
        ConfigDB().set(self, "*", "TRANSPORT", self.transport)
        ConfigDB().set(self, "*", "SEND_LOCK", self.send_lock)

        self.tx_agent = UARTTxAgent("tx_agent", self)
        self.rx_monitor = UARTRxMonitor("rx_monitor", self)
        self.scoreboard = LoopbackScoreboard("scoreboard", self)

    def connect_phase(self):
        self.tx_agent.driver.ap.connect(self.scoreboard.expected_export)
        self.rx_monitor.ap.connect(self.scoreboard.actual_export)


class UARTLoopbackBaseTest(uvm_test):
    SEQ_CLASS = Agent0Sequence
    EXPECTED_PACKETS_MULTIPLIER = 1

    def build_phase(self):
        self.env = UARTLoopbackEnv("env", self)

    def end_of_elaboration_phase(self):
        self.port = ConfigDB().get(self, "", "UART_PORT")
        self.baud_rate = ConfigDB().get(self, "", "UART_BAUD")
        self.count_per_agent = ConfigDB().get(self, "", "COUNT_PER_AGENT")
        self.timeout_s = ConfigDB().get(self, "", "LOOPBACK_TIMEOUT_S")

    def _expected_packets(self) -> int:
        return int(self.count_per_agent) * int(self.EXPECTED_PACKETS_MULTIPLIER)

    async def run_phase(self):
        self.raise_objection()
        await self.env.transport.open(self.port, self.baud_rate)

        try:
            expected_packets = self._expected_packets()
            print(
                f"[TEST CONFIG] {self.__class__.__name__} "
                f"port={self.port} baud={self.baud_rate} "
                f"count_per_agent={self.count_per_agent} expected_packets={expected_packets}"
            )

            seq = self.SEQ_CLASS.create("seq")
            await seq.start(self.env.tx_agent.seqr)
            await self.env.scoreboard.wait_done(timeout_s=self.timeout_s)
        finally:
            await self.env.transport.close()
            self.drop_objection()


class UARTLoopbackSmokeTest(UARTLoopbackBaseTest):
    pass


class UARTLoopbackShortBurstTest(UARTLoopbackBaseTest):
    """Kept ad-hoc for quick bring-up; use --count 4 or similar at runtime."""

