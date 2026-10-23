import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess

spec = importlib.util.spec_from_file_location('worker', Path(__file__).resolve().parents[1] / 'scripts/continuous.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class WorkerTests(unittest.TestCase):
    def test_timeout_becomes_failure(self):
        with patch.object(worker.subprocess, 'run', side_effect=subprocess.TimeoutExpired('shop', 180)):
            self.assertFalse(worker.run_check('shop')['ok'])

    def test_failed_shop_does_not_block_other_shop_or_next_cycle(self):
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            os.chdir(folder)
            try:
                with patch.dict(os.environ, MONITOR_CHECKS='2', MONITOR_INTERVAL='60'), patch.object(worker, 'run_check', side_effect=[{'ok': False}, {'ok': True}, {'ok': True}, {'ok': True}]) as check, patch.object(worker, 'persist') as persist, patch.object(worker.time, 'sleep') as sleep:
                    with self.assertRaises(RuntimeError):
                        worker.main()
                    self.assertEqual(check.call_count, 4)
                    self.assertEqual(persist.call_count, 2)
                    self.assertEqual(sleep.call_count, 1)
            finally:
                os.chdir(old)
