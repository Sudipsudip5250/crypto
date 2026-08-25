from __future__ import annotations

import importlib
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import mock_open, patch

from core.config import PROJECT_WALLET, load_config
from core.download import safe_extract_zip
from hardware.cpu import build_cmd


class ConfigurationTests(unittest.TestCase):
    def test_default_config_is_monero_cpu_profile(self) -> None:
        cfg = load_config(require_wallet=False)
        self.assertEqual(cfg["coin"], "monero")
        self.assertEqual(cfg["algorithm"], "rx/0")
        self.assertEqual(cfg["backend"], "cpu")
        self.assertEqual(cfg["wallet_address"], "")
        self.assertEqual(len(PROJECT_WALLET), 95)
        self.assertTrue(PROJECT_WALLET.startswith("4"))

    def test_non_monero_cannot_use_published_monero_wallet(self) -> None:
        with patch("core.config.CONFIG_PATH") as config_path:
            config_path.exists.return_value = True
            payload = '{"coin": "ravencoin", "wallet_address": "' + PROJECT_WALLET + '"}'
            with patch("builtins.open", mock_open(read_data=payload)):
                with self.assertRaises(SystemExit):
                    load_config()


class CommandBuilderTests(unittest.TestCase):
    def base_config(self) -> dict:
        return {
            "coin": "monero",
            "algorithm": "rx/0",
            "backend": "cpu",
            "cuda_devices": "",
            "opencl_devices": "",
            "pool_address": "pool.example:3333",
            "wallet_address": PROJECT_WALLET,
            "pool_password": "x",
            "worker_name": "test-rig",
            "cpu_usage_percent": 0.5,
            "cpu_priority": 2,
            "randomx_mode": "auto",
        }

    @patch("hardware.cpu.calculate_threads", return_value=4)
    def test_cpu_monero_command(self, _threads) -> None:
        cmd = build_cmd("xmrig", self.base_config())
        self.assertIn("--coin", cmd)
        self.assertIn("monero", cmd)
        self.assertIn("--threads", cmd)
        self.assertIn("--randomx-mode=auto", cmd)
        self.assertNotIn("--cuda", cmd)

    @patch("hardware.cpu.calculate_threads", return_value=4)
    def test_cuda_command_and_device_selection(self, _threads) -> None:
        cfg = self.base_config() | {
            "coin": "ravencoin",
            "algorithm": "kawpow",
            "backend": "cuda",
            "cuda_devices": "0,2",
        }
        cmd = build_cmd("xmrig", cfg)
        self.assertIn("--coin", cmd)
        self.assertIn("ravencoin", cmd)
        self.assertIn("--cuda", cmd)
        self.assertIn("--cuda-devices=0,2", cmd)
        self.assertNotIn("--threads", cmd)


class PlatformModuleTests(unittest.TestCase):
    def test_all_platform_modules_import(self) -> None:
        for name in ("platforms.linux", "platforms.windows", "platforms.macos"):
            module = importlib.import_module(name)
            self.assertTrue(hasattr(module, "ensure_xmrig"))
            self.assertTrue(hasattr(module, "launch_process"))

    def test_release_asset_names_are_versioned(self) -> None:
        windows = importlib.import_module("platforms.windows")
        linux = importlib.import_module("platforms.linux")
        macos = importlib.import_module("platforms.macos")
        self.assertIn("windows-x64.zip", windows._release_asset("6.26.0"))
        self.assertIn("msvc-win64.zip", windows._release_asset("6.22.2"))
        self.assertIn("linux-static-x64.tar.gz", linux.RELEASE_URL.format(version="6.26.0"))
        self.assertIn("macos-", macos._release_url("6.26.0"))


class ArchiveSafetyTests(unittest.TestCase):
    def test_zip_traversal_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            archive = Path(directory) / "bad.zip"
            destination = Path(directory) / "out"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("../../outside.txt", "blocked")
            with self.assertRaises(RuntimeError):
                safe_extract_zip(archive, destination)


if __name__ == "__main__":
    unittest.main()
