import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from alpha_poker_cli import dojo, main
from alpha_poker_cli.local_recap import Evidence


class DojoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'bot.json').write_text(json.dumps({'api_version':'2026-09-01','name':'Practice','language':'python','entrypoint':'bot.py:decide'}))
        (self.root/'bot.py').write_text("def decide(s):\n    return {'action': 'raise', 'amount': s['min_raise_to']} if 'raise' in s['legal_actions'] else {'action': 'check' if 'check' in s['legal_actions'] else 'call'}\n")
        self.env = patch.dict(os.environ, {'ALPHA_POKER_DOJO_STATE': str(self.root/'state.json')})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_offline_match_is_mirrored_and_uses_same_recap(self):
        with patch.object(main, '_http_json', side_effect=AssertionError('network is forbidden')), contextlib.redirect_stdout(io.StringIO()):
            path = dojo.run(self.root, 'pebble', 200, self.root/'run.zip')
        with zipfile.ZipFile(path) as archive:
            summary = json.loads(archive.read('summary.json'))
            hands = [json.loads(line) for line in archive.read('hands.jsonl').splitlines()]
        self.assertTrue(summary['qualified'])
        self.assertEqual(summary['bot_errors'], 0)
        self.assertEqual(hands[0]['hole_cards'], hands[1]['hole_cards'])
        self.assertEqual(hands[0]['players'], list(reversed(hands[1]['players'])))
        self.assertEqual(len(dojo.read_state()['runs']), 1)
        evidence = Evidence(path)
        self.assertTrue(evidence.complete)
        self.assertEqual(len(evidence.groups), 1)
        self.assertTrue(evidence.recap('0')['highlights'])
        self.assertTrue(evidence.recap('0', '199')['highlights'][0]['steps'])

    def test_invalid_counts_do_not_launch_student(self):
        for count in (0, 1, 3, 401, 402):
            with self.assertRaises(main.CliError), patch.object(main, '_load_bot', side_effect=AssertionError('must validate first')):
                dojo.run(self.root, 'pebble', count, self.root/'run.zip')

    def test_bot_errors_are_retained_and_never_qualify(self):
        (self.root/'bot.py').write_text("def decide(s):\n    raise RuntimeError('test bot error')\n")
        with contextlib.redirect_stdout(io.StringIO()):
            path = dojo.run(self.root, 'pebble', 200, self.root/'errors.zip')
        with zipfile.ZipFile(path) as archive:
            summary = json.loads(archive.read('summary.json'))
        self.assertFalse(summary['qualified'])
        self.assertGreater(summary['bot_errors'], 0)
        self.assertEqual(summary['hands_played'], 200)

    def test_existing_evidence_is_not_overwritten(self):
        path = self.root/'existing.zip'
        path.write_bytes(b'preserve me')
        with self.assertRaises(main.CliError), patch.object(main, '_load_bot', side_effect=AssertionError('must validate output first')):
            dojo.run(self.root, 'pebble', 200, path)
        self.assertEqual(path.read_bytes(), b'preserve me')

    def test_parser_preserves_leader_and_accepts_packaged_choices(self):
        parser = main._parser()
        self.assertEqual(parser.parse_args(['train']).opponent, 'leader')
        for name in dojo.IDS:
            self.assertEqual(parser.parse_args(['train','--opponent',name]).opponent, name)

    def test_local_list_never_needs_network(self):
        with patch.object(main, '_http_json', side_effect=AssertionError('network')), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main.main(['dojo','list','--offline','--json']), 0)
        self.assertEqual(len(json.loads(output.getvalue())['bots']), 5)
