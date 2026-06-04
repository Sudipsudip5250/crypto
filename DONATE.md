# Support & Donations

This project is free and open-source. If it has been useful to you, you can
support it in two ways — by donating your spare CPU time or by sending XMR directly.

---

## Option 1 — Mine for the project (donate CPU time)

The default `config.json` already points to the project wallet.
If you have not changed `wallet_address`, you are already donating every hash you mine.

```bash
./mine.sh start      # foreground
./mine.sh bg         # background daemon
```

To donate for a quick session without changing your own config:

```bash
python miner.py --donate
```

This temporarily overrides your wallet with the project wallet for that session only.
Your `config.json` is not modified.

---

## Option 2 — Send XMR directly

**Monero (XMR) wallet address:**

```
4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU
```

You can send any amount of XMR to this address from any Monero wallet
(Feather Wallet, MyMonero, the official CLI wallet, etc.).

### Verify earnings on the pool dashboard

Mining donations are visible in real time at:

```
https://supportxmr.com/#/dashboard?addr=4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU
```

---

## Why Monero?

Monero (XMR) is the only major cryptocurrency specifically designed for
CPU mining (via the RandomX algorithm). It is privacy-focused and can be
mined on any modern CPU — no GPU required.

---

## Thank you

Every hash counts. Whether you mine for a minute or leave it running overnight,
it is genuinely appreciated.
