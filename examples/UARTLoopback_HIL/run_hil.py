#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from pyuvm import ConfigDB, uvm_root

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import testbench


def _resolve_test_class(test_name: str):
    try:
        cls = getattr(testbench, test_name)
    except AttributeError as exc:
        raise ValueError(f"Unknown test class: {test_name}") from exc
    return cls


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UART loopback pyuvm HIL example")
    parser.add_argument("--port", required=True, help="Serial port, e.g. COM5")
    parser.add_argument("--baud", type=int, default=115200, help="UART baud rate")
    parser.add_argument(
        "--count",
        type=int,
        default=16,
        help="Packets sent by TX agent",
    )
    parser.add_argument(
        "--test",
        default="UARTLoopbackSmokeTest",
        help="Python test class name in testbench.py",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=10.0,
        help="Scoreboard wait timeout in seconds",
    )
    return parser.parse_args()


async def _main() -> None:
    args = parse_args()

    ConfigDB().set(None, "*", "UART_PORT", args.port)
    ConfigDB().set(None, "*", "UART_BAUD", args.baud)
    ConfigDB().set(None, "*", "COUNT_PER_AGENT", args.count)
    ConfigDB().set(None, "*", "EXPECTED_PACKETS", args.count)
    ConfigDB().set(None, "*", "LOOPBACK_TIMEOUT_S", args.timeout_s)

    test_cls = _resolve_test_class(args.test)

    await uvm_root().run_test(test_cls, keep_set={ConfigDB})


if __name__ == "__main__":
    asyncio.run(_main())
