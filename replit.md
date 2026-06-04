# XMR Miner

Cross-platform Monero (XMR) miner controller. For education and research purposes.

## Overview

A modular Python controller that auto-downloads XMRig and mines Monero
across Linux, Windows, and macOS from a single entry point.

## Project Layout

```
miner.py              ← single entry point (run this)
config.json           ← all user settings (wallet, pool, temp, timing)

core/
  config.py           — load / save / interactive wizard
  logger.py           — logging setup
  requirements.py     — auto-installs missing pip packages on startup

platforms/
  detect.py           — OS + arch detection
  linux.py            — static binary download, PTY launch
  windows.py          — zip download, subprocess launch
  macos.py            — arm64/x64 download, PTY launch, brew fallback

hardware/
  cpu.py              — thread count, affinity, priority, cmd builder
  gpu.py              — GPU detection (OpenCL/CUDA stubs for future)

controller/
  process.py          — start / stop / health-check XMRig
  thermal.py          — temp monitoring, suspend / resume / kill
  duty_cycle.py       — timed mine→rest cycles

tools/                ← XMRig binary auto-downloaded here (gitignored)
logs/                 ← miner.log (gitignored)
safe_mine/            ← original safe_mine repo (kept as reference)
```

## Usage

```bash
python miner.py            # start mining
python miner.py --setup    # interactive config wizard
python miner.py --info     # show OS / CPU / GPU info
```

## Tools Installed

- **opencode** — available as `opencode` in the terminal

## User Preferences

(none set)
