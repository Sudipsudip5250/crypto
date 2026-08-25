# Per-worker and group configuration

Each local worker should use its own configuration file. This is useful for a group of people who have permission to share a machine, but it does not create a remote mining controller or a shared wallet service.

Create a private config file with the setup wizard:

```bash
python miner.py --config configs/alice.json setup
python miner.py --config configs/alice.json check
python miner.py --config configs/alice.json bg
```

The `configs/*.json` pattern is ignored by Git so wallet addresses, pool passwords, and worker-specific settings are not committed accidentally. Keep file permissions private on shared Linux systems, and never paste a wallet seed phrase or private key into this project. Only wallet addresses and pool credentials belong in the configuration.

For another authorized worker, use a different file and worker name:

```bash
python miner.py --config configs/bob.json setup
python miner.py --config configs/bob.json check
```

Separate config files receive separate PID and log names. Everyone must use hardware they own or are explicitly authorized to use, and every person must agree to the selected wallet, pool, coin, resource limits, and operating schedule before starting a worker. The project does not provide remote administration, automatic wallet sharing, or hidden execution.
