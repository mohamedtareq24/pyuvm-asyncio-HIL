# HIL Install and Fork Verification Tutorial

This quick tutorial installs the asyncio HIL fork of pyuvm and verifies that
your environment is using the expected source.

## 1) Install dependencies

```bash
pip install "git+https://github.com/mohamedtareq24/pyuvm-asyncio-HIL@asyncio-hil"
pip install "pyserial-asyncio>=0.6"
```

## 2) Verify the pyuvm source

Run the helper script from the repository root:

```bash
python hil_fork_test/verify_pyuvm_fork.py
```

Expected success line:

```text
PASS: pyuvm installed from pyuvm-asyncio-HIL fork
```

## 3) Optional: override expected repo

PowerShell:

```powershell
$env:EXPECTED_PYUVM_REPO = "mohamedtareq24/pyuvm-asyncio-HIL"
python hil_fork_test/verify_pyuvm_fork.py
```

Bash:

```bash
EXPECTED_PYUVM_REPO="mohamedtareq24/pyuvm-asyncio-HIL" python hil_fork_test/verify_pyuvm_fork.py
```

The verification script used in this tutorial is:
`hil_fork_test/verify_pyuvm_fork.py`