# XMR Miner

> **⚠️ FOR EDUCATIONAL AND RESEARCH PURPOSES ONLY**
> Do **not** run this on cloud platforms (AWS, GCP, Azure, Replit, DigitalOcean, etc.) —
> it violates their Terms of Service and will get your account suspended.
> See **[DISCLAIMER.md](DISCLAIMER.md)** for the full legal notice.

Cross-platform Monero (XMR) miner controller built on [XMRig](https://github.com/xmrig/xmrig).
Supports **Linux · Windows · macOS** — for education and research purposes only.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## Support & Donations

This project is free and open-source. You can support it by donating CPU time or sending XMR directly.

**Monero (XMR) wallet:**
```
4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU
```

| Method | How |
|--------|-----|
| **Mine to donate** | The default `config.json` already points to this wallet. Leave it unchanged and every hash goes to the project. |
| **Quick donate session** | `python miner.py donate-mode` mines to the project wallet for 10 min without changing your config. Pass minutes: `python miner.py donate-mode --donate-time 30` |
| **Show donation info** | `python miner.py donate` prints the wallet and full details |
| **Send XMR directly** | Paste the address above into any Monero wallet (Feather, MyMonero, CLI) |
| **Verify donations** | [SupportXMR pool dashboard](https://supportxmr.com/#/dashboard?addr=4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU) |

See **[DONATE.md](DONATE.md)** for full details.

---

## Quick Start

### Linux / macOS
```bash
chmod +x mine.sh
./mine.sh setup          # configure wallet, pool, temperature limits
./mine.sh bg             # mine in background (daemon)
./mine.sh status         # check if running
./mine.sh logs           # watch live log output
./mine.sh stop           # stop background miner
```

### Windows (Command Prompt)
```bat
mine setup
mine bg
mine status
mine stop
```

### Windows (PowerShell)
```powershell
.\mine.ps1 setup
.\mine.ps1 bg
.\mine.ps1 status
.\mine.ps1 stop
```

### Direct Python (any OS)
```bash
python miner.py setup     # interactive config wizard
python miner.py           # start mining (foreground)
python miner.py bg        # start mining (background)
python miner.py help      # full command reference
```

> **Note:** Python dependencies (`psutil`) are installed automatically on first run.
> No manual `pip install` is needed.

---

## CLI Reference

All commands are the same whether you use `mine.sh`, `mine.bat`, `mine.ps1`,
or `python miner.py` directly — the shell scripts are thin launchers that
pass everything through to `miner.py`.

| Command | Description |
|---------|-------------|
| `start` | Start mining in the **foreground** — Ctrl+C to stop |
| `bg` | Start mining in the **background** (daemon / detached process) |
| `stop` | Stop a background miner gracefully (SIGTERM → SIGKILL) |
| `restart` | Stop + start in the background |
| `status` | Show running state and last 5 log lines |
| `logs` | Tail the log file in real time (Ctrl+C to exit) |
| `setup` | Interactive config wizard |
| `info` | Print OS, CPU model, core count, GPU detection |
| `version` | Show cached and latest XMRig version |
| `update` | Update XMRig to the latest GitHub release |
| `donate` | Show donation wallet and instructions |
| `donate-mode` | Mine to project wallet for N min (no config change) |
| `config` | Open `config.json` in your editor |
| `install` | Install / upgrade Python dependencies |
| `reset` | Delete cached XMRig binary (re-downloaded on next start) |
| `help` | Show command reference |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--donate-time MINUTES` | `10` | Duration for `donate-mode` |
| `--force-update` | — | Re-download XMRig even if up-to-date |

---

## Project Layout

```
.
├── mine.sh               ← thin launcher — Linux / macOS  (finds Python, calls miner.py)
├── mine.bat              ← thin launcher — Windows CMD
├── mine.ps1              ← thin launcher — Windows PowerShell
├── miner.py              ← all logic lives here (commands, mining loops, daemon mgmt)
├── config.json           ← all your settings
├── requirements.txt
├── LICENSE
├── DISCLAIMER.md         ← cloud-platform ToS warning (read before using)
├── DONATE.md
│
├── core/
│   ├── config.py         ← load / save / interactive wizard for config.json
│   ├── daemon.py         ← cross-platform bg / stop / status / logs / reset / …
│   ├── logger.py         ← logging setup (console + file, path-safe)
│   ├── requirements.py   ← auto-check and pip-install missing packages
│   └── updater.py        ← XMRig version check and download
│
├── platforms/
│   ├── detect.py         ← OS + arch detection, routes to right module
│   ├── linux.py          ← Linux:   static binary download, PTY launch
│   ├── windows.py        ← Windows: zip download, plain subprocess launch
│   └── macos.py          ← macOS:   arm64/x64 download, PTY launch, brew fallback
│
├── hardware/
│   ├── cpu.py            ← CPU info, thread count, affinity, XMRig cmd builder
│   └── gpu.py            ← GPU detection (stubs only — GPU mining not yet implemented)
│
├── controller/
│   ├── process.py        ← start / stop / health-check XMRig
│   ├── thermal.py        ← temperature monitoring, suspend / resume / kill
│   └── duty_cycle.py     ← timed mine-N-min → rest-M-min cycles
│
├── tools/                ← XMRig binary auto-downloaded here  (gitignored)
└── logs/                 ← miner.log written here             (gitignored)
```

---

## Configuration (`config.json`)

Run `python miner.py setup` for a guided wizard, or edit `config.json` directly.

### Pool & Identity

| Key | Default | Description |
|-----|---------|-------------|
| `wallet_address` | *project wallet* | Your XMR wallet address |
| `worker_name` | `myrig` | Rig label shown on the pool dashboard |
| `pool_address` | `pool.supportxmr.com:3333` | Pool `host:port` |
| `pool_password` | `x` | Pool password (usually `x`) |

> The default `wallet_address` in `config.json` is the project donation wallet.
> Replace it with your own address to mine for yourself.

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
Run `python miner.py reset` to delete the cache and force a fresh download.

---

## Features

| Feature | Status | Description |
|---------|--------|-------------|
| **Auto-setup** | ✅ | Downloads and installs XMRig automatically |
| **Cross-platform** | ✅ | Linux, Windows, macOS — one codebase |
| **Thin launchers** | ✅ | `mine.sh` / `mine.bat` / `mine.ps1` are ~25-line wrappers; all logic in Python |
| **Config wizard** | ✅ | `python miner.py setup` walks through every setting with validation |
| **Background daemon** | ✅ | `python miner.py bg/stop/status/logs` — cross-platform daemon management |
| **Thermal protection** | ✅ | Suspends, resumes, or kills the miner based on CPU temperature |
| **Duty-cycle mode** | ✅ | Mine N minutes → rest M minutes → repeat |
| **GPU detection** | 🔄 | Probes for NVIDIA / AMD / OpenCL — **GPU mining not yet implemented** |
| **Requirements check** | ✅ | Missing Python packages auto-installed on startup |
| **Donate mode** | ✅ | Mine to project wallet for a timed session without changing your config |

---

## Legal & License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE).

**Key restrictions:**

- 🚫 **Do not run on cloud platforms** — AWS, GCP, Azure, DigitalOcean, Linode, Heroku,
  Replit, Vercel, Netlify, GitHub Actions, GitHub Codespaces, or any hosted runner.
  These services prohibit cryptocurrency mining in their Terms of Service. In
  particular, never use GitHub Actions, Codespaces, GitHub-hosted runners, or
  self-hosted runners to execute this miner.
- 🚫 **Do not run on hardware you do not own** without explicit written permission.
- ⚠️ **Check local laws** — the legal status of cryptocurrency mining varies by jurisdiction.
- ⚠️ **Tax obligations** — mining income may be taxable in your country.

The author(s) accept **no liability** for ToS violations, account suspensions,
legal consequences, or any other damages arising from use of this software.

See **[DISCLAIMER.md](DISCLAIMER.md)** for the complete legal notice.
