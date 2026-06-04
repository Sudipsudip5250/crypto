# crypto

A Windows-oriented cryptocurrency mining automation project using XMRig 6.22.2.

## Overview

Python scripts that automate running, monitoring, and cycling the XMRig Monero (XMR) miner. Features include:
- CPU temperature monitoring via Core Temp
- Dynamic thread adjustment based on temperature thresholds
- 15-minute mining / 5-minute cooldown duty cycles
- Graceful shutdown on keypress

## Key Scripts

- `start_miner.py` — Simple restart-on-crash loop for XMRig
- `cycle_miner.py` — Duty-cycle miner with temperature monitoring
- `super_cycle_miner.py` / `super_cycle_miner_2.py` — Advanced versions with dynamic thread control

## Notes

- **Windows only**: The miner binary (`xmrig-6.22.2/xmrig.exe`) and temperature monitoring (`C:/Program Files/Core Temp/coretemp.txt`) are Windows-specific and will not run on Linux/Replit.
- Pool: `pool.supportxmr.com:443`

## User Preferences

(none set)
