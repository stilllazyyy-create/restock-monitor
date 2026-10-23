import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('recovery', Path(__file__).resolve().parents[1] / 'scripts/recover_scheduler.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveryTests(unittest.TestCase):
    def test_does_not_cancel_run_with_changed_identity(self):
        calls = []
        def call(path, method='GET'):
            calls.append((path, method))
            return {'workflow_id': 123, 'status': 'queued', 'created_at': '2026-09-15T09:25:06Z'}
        with self.assertRaisesRegex(RuntimeError, 'identity/status'):
            recovery.cancel_orphan(call, lambda _: None)
        self.assertTrue(all(method == 'GET' for _, method in calls))

    def test_normal_cancellation_succeeds_without_force(self):
        calls = []
        def call(path, method='GET'):
            calls.append((path, method))
            if method == 'POST':
                return None
            if len(calls) == 1:
                return {'workflow_id': recovery.WORKFLOW_ID, 'status': 'queued', 'created_at': '2026-09-15T09:25:06Z'}
            return {'status': 'completed', 'conclusion': 'cancelled'}
        self.assertIn('cleared', recovery.cancel_orphan(call, lambda _: None))
        self.assertFalse(any('force-cancel' in path for path, _ in calls))

    def test_reset_reenables_even_when_disable_response_fails(self):
        calls = []
        def call(path, method='GET'):
            calls.append(path)
            if path.endswith('/disable'):
                raise RuntimeError('ambiguous timeout')
        with self.assertRaises(RuntimeError):
            recovery.reset_schedule(call)
        self.assertTrue(calls[-1].endswith('/enable'))


if __name__ == '__main__':
    unittest.main()
