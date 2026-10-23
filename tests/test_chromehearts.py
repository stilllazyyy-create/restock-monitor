import contextlib
import io
import json
from pathlib import Path
import os
import runpy
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/chromehearts.py'
OLD = '/scarf/old/1.html'
NEW = '/scarf/new/2.html'


class Response:
    status = 200

    def __init__(self, content):
        self.content = content.encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return self.content


class MonitorTests(unittest.TestCase):
    def run_monitor(self, pages, state=None, discord_fails=False):
        sent = []

        def fetch(request, **kwargs):
            if request.get_method() == 'POST':
                if discord_fails:
                    raise urllib.error.URLError('Discord unavailable')
                sent.append(json.loads(request.data)['content'])
                return Response('')
            content = pages[request.full_url]
            if isinstance(content, Exception):
                raise content
            return Response(content)

        with tempfile.TemporaryDirectory() as folder:
            previous_cwd = os.getcwd()
            os.chdir(folder)
            try:
                file = Path('.chromehearts_state.json')
                if state is not None:
                    file.write_text(json.dumps(state))
                error = None
                with patch.dict(os.environ, CHROME_HEARTS_WEBHOOK_URL='https://example.invalid/webhook'), patch('urllib.request.urlopen', side_effect=fetch), patch('time.sleep'), contextlib.redirect_stdout(io.StringIO()):
                    try:
                        runpy.run_path(str(SCRIPT), run_name='__main__')
                    except Exception as caught:
                        error = caught
                result = json.loads(file.read_text()) if file.exists() else None
            finally:
                os.chdir(previous_cwd)
        return result, sent, error

    def initial_state(self):
        return {
            'initialized': True,
            'known_categories': ['/scarf', '/scents'],
            'online_categories': ['/scarf', '/scents'],
            'current_products_by_category': {'/scarf': [OLD], '/scents': ['/scents/old/3.html']},
            'ever_seen_products_by_category': {'/scarf': [OLD], '/scents': ['/scents/old/3.html']},
        }

    def pages(self):
        return {
            'https://www.chromehearts.com/': '<a href="/scarf">Scarf</a><a href="/scents">Scents</a>',
            'https://www.chromehearts.com/scarf': f'<a href="{OLD}">Old</a><a href="{NEW}">New</a>',
            'https://www.chromehearts.com/scents': '<a href="/scents/new/4.html">New scent</a>',
        }

    def test_one_failed_category_does_not_suppress_clothing_alert(self):
        pages = self.pages()
        pages['https://www.chromehearts.com/scents'] = urllib.error.URLError('offline')
        result, sent, error = self.run_monitor(pages, self.initial_state())
        self.assertEqual(len(sent), 1)
        self.assertIn(NEW, sent[0])
        self.assertIn(NEW, result['current_products_by_category']['/scarf'])
        self.assertEqual(result['current_products_by_category']['/scents'], ['/scents/old/3.html'])
        self.assertIn('/scents', result['failed_categories'])
        self.assertIsInstance(error, RuntimeError)

    def test_discord_failure_keeps_old_state_for_retry(self):
        state = self.initial_state()
        result, sent, error = self.run_monitor(self.pages(), state, discord_fails=True)
        self.assertEqual(result, state)
        self.assertEqual(sent, [])
        self.assertIsNotNone(error)

    def test_permanent_ranges_do_not_notify_and_no_duplicate_next_run(self):
        result, sent, error = self.run_monitor(self.pages(), self.initial_state())
        self.assertIsNone(error)
        self.assertEqual(len(sent), 1)
        self.assertNotIn('scents', sent[0])
        self.assertTrue(result['last_complete_check_at'])
        _, sent, error = self.run_monitor(self.pages(), result)
        self.assertEqual(sent, [])
        self.assertIsNone(error)

    def test_first_run_baselines_without_alerting_old_products(self):
        result, sent, error = self.run_monitor(self.pages())
        self.assertEqual(sent, [])
        self.assertIsNone(error)
        self.assertTrue(result['initialized'])

    def test_new_category_that_failed_is_still_new_when_it_recovers(self):
        pages = self.pages()
        pages['https://www.chromehearts.com/'] += '<a href="/t-shirts">T-shirts</a>'
        pages['https://www.chromehearts.com/t-shirts'] = urllib.error.URLError('offline')
        result, _, error = self.run_monitor(pages, self.initial_state())
        self.assertIsNotNone(error)
        self.assertNotIn('/t-shirts', result['known_categories'])
        pages['https://www.chromehearts.com/t-shirts'] = '<a href="/t-shirts/new/5.html">T-shirt</a>'
        result, sent, error = self.run_monitor(pages, result)
        self.assertIsNone(error)
        self.assertTrue(any('新分类上线' in message and 't-shirts' in message for message in sent))


if __name__ == '__main__':
    unittest.main()
