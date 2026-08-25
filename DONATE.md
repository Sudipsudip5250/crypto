# Support & Donations

This project is free and open-source. If it has been useful to you, you can
support it in two ways — by donating your spare CPU time or by sending XMR directly.

---

## Option 1 — Mine for the project (donate CPU time)

The normal `config.json` wallet is intentionally empty until you run setup.
For an explicit donation session that does not change your configuration, use
`python miner.py donate-mode` as described below.

```bash
./mine.sh start      # foreground
./mine.sh bg         # background daemon
```

To donate for a quick session without changing your own config:

```bash
# Linux / macOS
./mine.sh donate-mode           # 10-minute session (default)
./mine.sh donate-mode 30        # 30-minute session

# Windows
mine donate-mode                # 10-minute session
mine donate-mode 30             # 30-minute session

# Any platform via Python directly
python miner.py --donate-mode                  # 10-minute session
python miner.py --donate-mode --donate-time 30 # 30-minute session
```

This temporarily overrides your wallet with the project wallet for that session only.
Your `config.json` is never modified.

---

## Option 2 — Send XMR directly

**Monero (XMR) wallet address:**

```
4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU
```

You can send any amount of **XMR only** to this address from any Monero wallet
(Feather Wallet, MyMonero, the official CLI wallet, etc.). Do not send BTC, RVN,
RTM, or any other cryptocurrency to this Monero address.

This address is intentionally public in `README.md`, `DONATE.md`, and the
`python miner.py donate` command so supporters can verify and use it. It is not
copied into the normal `config.json`, which stays empty until a user configures
an address.

### Verify earnings on the pool dashboard

Mining donations are visible in real time at:

```
https://supportxmr.com/#/dashboard?addr=4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU
```

---

## Other coins and custom profiles

The controller can pass supported XMRig coin aliases and algorithms to the local
XMRig binary. Run `python miner.py setup`, select `ravencoin`, `raptoreum`, or
`custom`, and provide a wallet and pool that belong to that coin. The published
project address remains Monero-only and is never reused for another coin.

Coin support depends on the selected XMRig release, the pool, the algorithm,
local hardware, and installed CUDA/OpenCL drivers or plugins. The project does
not provide profit switching, hidden mining, automatic wallet creation, or hosted
mining; every run must be started by the local user on permitted hardware.

---

## Why Monero?

Monero (XMR) is the only major cryptocurrency specifically designed for
CPU mining (via the RandomX algorithm). It is privacy-focused and can be
mined on any modern CPU — no GPU required.

---

## Thank you

Every hash counts. Whether you mine for a minute or leave it running overnight,
it is genuinely appreciated.
