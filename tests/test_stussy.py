import ast
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/stussy.py'
TARGETS = next(ast.literal_eval(node.value) for node in ast.parse(SCRIPT.read_text()).body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'TARGETS' for target in node.targets))
VARIANTS = [{'id': key, 'title': title, 'available': True} for target in TARGETS for key, title in target['variants'].items()]


class Response:
    status = 200
    def __init__(self, data):
        self.data = json.dumps(data).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self):
        return self.data


class StussyTests(unittest.TestCase):
    def run_monitor(self, discord_fails=False, invalid_stock=False, corrupt=False):
        state = {f'variant_{v["id"]}': False for v in VARIANTS}
        state.update(new_arrivals_ever_seen=[], new_arrivals_ever_seen_handles=[])
        sent = []
        def fetch(request, **kwargs):
            if request.get_method() == 'POST':
                if discord_fails:
                    raise urllib.error.URLError('offline')
                sent.append(json.loads(request.data))
                return Response({})
            if '/products.json?' in request.full_url:
                return Response({'products': []})
            variants = [dict(v, available='unknown') for v in VARIANTS] if invalid_stock else VARIANTS
            return Response({'variants': variants, 'title': 'Test', 'images': []})
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            os.chdir(folder)
            try:
                path = Path('.restock_state.json')
                path.write_text('broken' if corrupt else json.dumps(state))
                error = None
                with patch.dict(os.environ, DISCORD_WEBHOOK_URL='https://example.invalid/webhook'), patch('urllib.request.urlopen', side_effect=fetch), patch('time.sleep'), contextlib.redirect_stdout(io.StringIO()):
                    try:
                        runpy.run_path(str(SCRIPT), run_name='__main__')
                    except Exception as caught:
                        error = caught
                content = path.read_text()
                return json.loads(content) if not corrupt else content, sent, error
            finally:
                os.chdir(old)

    def test_delivery_failure_is_visible_and_preserves_retry_state(self):
        state, sent, error = self.run_monitor(discord_fails=True)
        self.assertIsInstance(error, RuntimeError)
        self.assertFalse(state['variant_' + str(VARIANTS[0]['id'])])
        self.assertTrue(state['check_errors'])
        self.assertEqual(sent, [])

    def test_success_records_heartbeat_after_confirmed_delivery(self):
        state, sent, error = self.run_monitor()
        self.assertIsNone(error)
        self.assertTrue(state['last_complete_check_at'])
        self.assertEqual(len(sent), len(VARIANTS))

    def test_unknown_availability_does_not_overwrite_stock(self):
        state, sent, error = self.run_monitor(invalid_stock=True)
        self.assertIsInstance(error, RuntimeError)
        self.assertFalse(state['variant_' + str(VARIANTS[0]['id'])])
        self.assertEqual(sent, [])

    def test_corrupt_state_does_not_reset_baseline(self):
        content, sent, error = self.run_monitor(corrupt=True)
        self.assertIsInstance(error, json.JSONDecodeError)
        self.assertEqual(content, 'broken')
        self.assertEqual(sent, [])
