# XMR Miner

Cross-platform Monero (XMR) miner controller built on XMRig.
Supports **Linux · Windows · macOS** — for education and research purposes.

---

## Quick Start

```bash
# 1. Install Python dependencies
pip install psutil

# 2. Configure (interactive setup)
python miner.py --setup

# 3. Mine
python miner.py

# 4. Check system info (OS, CPU, GPU detection)
python miner.py --info
```

---

## Project Layout

```
.
├── miner.py              ← single entry point (run this)
├── config.json           ← all your settings
├── requirements.txt
├── README.md
│
├── core/
│   ├── config.py         ← load / save / interactive wizard for config.json
│   ├── logger.py         ← logging setup (console + file)
│   └── requirements.py   ← auto-check and pip-install missing packages
│
├── platforms/
│   ├── detect.py         ← OS + arch detection, routes to right module
│   ├── linux.py          ← Linux:   static binary download, PTY launch
│   ├── windows.py        ← Windows: zip download, plain subprocess launch
│   └── macos.py          ← macOS:   arm64/x64 download, PTY launch, brew fallback
│
├── hardware/
│   ├── cpu.py            ← CPU info, thread count, affinity, XMRig cmd builder
│   └── gpu.py            ← GPU detection stubs (OpenCL / CUDA — future use)
│
├── controller/
│   ├── process.py        ← start / stop / health-check XMRig
│   ├── thermal.py        ← temperature monitoring, suspend / resume / kill
│   └── duty_cycle.py     ← timed mine-N-min → rest-M-min cycles
│
├── tools/                ← XMRig binary auto-downloaded here (gitignored)
├── logs/                 ← miner.log written here (gitignored)
└── safe_mine/            ← original safe_mine repo (reference / development)
```

---

## Configuration (`config.json`)

Edit `config.json` directly or run `python miner.py --setup` for a guided wizard.

### Pool & Identity

| Key | Default | Description |
|-----|---------|-------------|
| `wallet_address` | *(required)* | Your XMR wallet address |
| `worker_name` | `myrig` | Rig label shown on the pool dashboard |
| `pool_address` | `pool.supportxmr.com:3333` | Pool `host:port` |
| `pool_password` | `x` | Pool password (usually `x`) |

### CPU Resource Limits

| Key | Default | Description |
|-----|---------|-------------|
| `cpu_usage_percent` | `0.70` | Fraction of CPU cores to use (0.1 – 1.0) |
| `randomx_mode` | `auto` | RandomX mode: `auto` / `light` / `hard` |
| `cpu_priority` | `2` | Process priority 0 (lowest) → 5 (highest) |

### Thermal Protection

| Key | Default | Description |
|-----|---------|-------------|
| `pause_temp_c` | `80` | Suspend miner above this CPU temp (°C) |
| `resume_temp_c` | `70` | Resume miner below this CPU temp (°C) |
| `emergency_kill_temp_c` | `90` | Kill miner + exit above this temp (°C) |
| `temp_check_interval_sec` | `20` | How often to check temperature (seconds) |

### Duty-Cycle Mode

| Key | Default | Description |
|-----|---------|-------------|
| `duty_cycle_enabled` | `false` | `true` = timed on/off cycles |
| `mine_duration_min` | `15` | Minutes to mine per cycle |
| `rest_duration_min` | `5` | Minutes to rest per cycle |

### Other

| Key | Default | Description |
|-----|---------|-------------|
| `xmrig_version` | `6.22.2` | XMRig release to auto-download |
| `log_to_file` | `true` | Also write logs to `logs/miner.log` |

---

## How XMRig is Obtained

No binary is bundled — XMRig is fetched automatically on first run.

| OS | Method |
|----|--------|
| **Linux** | Downloads static x64 binary from GitHub; falls back to `apt` / `dnf` / `pacman` / `zypper` |
| **Windows** | Downloads MSVC Win64 zip from GitHub, unpacks to `tools/xmrig/` |
| **macOS** | Downloads arm64 or x64 tar.gz from GitHub; falls back to `brew install xmrig` |

The binary is cached in `tools/xmrig/` and reused on subsequent runs.

---

## Features

| Feature | Description |
|---------|-------------|
| **Auto-setup** | Downloads and installs XMRig automatically — no manual binary setup |
| **Cross-platform** | One entry point, three OS-specific platform modules |
| **Config wizard** | `python miner.py --setup` walks through every setting |
| **Thermal protection** | Suspends, resumes, or kills the miner based on CPU temperature |
| **Duty-cycle mode** | Mine N minutes → rest M minutes → repeat |
| **GPU detection** | Probes for NVIDIA / AMD / OpenCL GPUs (GPU mining hooks ready for future) |
| **Requirements check** | Missing Python packages are installed automatically on startup |
| **Clean logging** | Console + optional `logs/miner.log` |

---

## Disclaimer

This project is for **educational and research purposes only**.
Mining uses significant CPU resources and electricity.
Only run on hardware you own or have explicit permission to use.
