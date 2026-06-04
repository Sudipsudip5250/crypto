# XMR Miner

Cross-platform Monero (XMR) miner controller. For education and research purposes.

## Overview

A single unified Python controller (`miner.py`) that:
- Auto-downloads the correct XMRig binary for your OS (Linux, Windows, macOS)
- Reads all settings from `config.json` — no code editing needed
- Monitors CPU temperature and suspends/kills the miner at thresholds
- Supports optional duty-cycle mode (mine N min → rest M min → repeat)
- Logs to console and `logs/miner.log`

## Project Layout

```
.
├── miner.py          ← entry point
├── config.json       ← all your settings (wallet, pool, temp limits, etc.)
├── requirements.txt  ← psutil
├── README.md
├── tools/            ← XMRig binary auto-downloaded here (gitignored)
└── logs/             ← miner.log written here (gitignored)
```

## Usage

```bash
# Interactive setup (first time)
python miner.py --setup

# Start mining
python miner.py
```

## Key Config Options (config.json)

- `wallet_address` — your XMR wallet
- `worker_name` — rig label shown on the pool
- `pool_address` — mining pool (default: pool.supportxmr.com:3333)
- `cpu_usage_percent` — fraction of cores to use (0.1 – 1.0)
- `duty_cycle_enabled` — true = mine/rest cycles, false = continuous
- `mine_duration_min` / `rest_duration_min` — cycle timing
- `pause_temp_c` / `resume_temp_c` / `emergency_kill_temp_c` — thermal protection
- `xmrig_version` — which XMRig release to fetch from GitHub

## Tools Installed

- **opencode** CLI — available as `opencode` in terminal for AI assistance

## User Preferences

(none set)
