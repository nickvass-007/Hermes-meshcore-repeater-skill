"""Offline safety regression tests. Never contact a real radio or load real credentials."""
import importlib.util
import io
import json
import os
from pathlib import Path
import ssl
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/repeater_cmd.py'
spec = importlib.util.spec_from_file_location('meshcore_test_module', SCRIPT)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
A = 'a1b2c3' + '0' * 58
B = 'd4e5f6' + '1' * 58
C = 'a1b2c3' + '2' * 58

def contact(key, kind=2, name='Test repeater'):
    return {'public_key': key, 'type': kind, 'favorite': False, 'name': name}

class FakeClient:
    def __init__(self, contacts=None, replies=None):
        self.inventory = contacts if contacts is not None else [contact(A), contact(B)]
        self.replies = replies or {}
        self.calls = []
        self.login_failure = False
    def health(self):
        self.calls.append(('health',))
    def contacts(self):
        self.calls.append(('contacts',))
        return self.inventory
    def login(self, pk, password):
        self.calls.append(('login', pk))
        if self.login_failure:
            raise m.SafetyError('Login was not confirmed.')
    def command_once(self, pk, command):
        self.calls.append(('command', pk, command))
        if (pk, command) in self.replies:
            values = self.replies[(pk, command)]
            response = values.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        if command == 'get public.key':
            return '> ' + pk
        if command == 'ver':
            return 'v1.test (Build: offline)'
        raise AssertionError('Unplanned simulated command: ' + command)

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / 'state'
        self.cfg = m.Config('https://radio.invalid', {'MESHCORE_REPEATER_PASSWORD': 'FAKE_SECRET_8129'})
        self.sleep = patch.object(m.time, 'sleep', lambda _: None)
        self.sleep.start()
    def tearDown(self):
        self.sleep.stop()
        self.temp.cleanup()
    def run_op(self, fake, command='set int.thresh 0', selectors=None, apply=True, disruptive=False):
        return m.operate(fake, self.cfg, selectors or ['a1b2c3'], m.classify(command), apply, disruptive, self.state)
    def test_unique_six_hex_resolves_full_key_non_favourite(self):
        self.assertEqual(m.resolve_targets(['A1B2C3'], [contact(A)])[0]['public_key'], A)
    def test_prefix_collision_in_non_repeater_is_not_hidden(self):
        with self.assertRaises(m.SafetyError):
            m.resolve_targets(['a1b2c3'], [contact(A), contact(C, 1)])
    def test_collision_full_key_resolves(self):
        self.assertEqual(m.resolve_targets([A], [contact(A), contact(C)])[0]['public_key'], A)
    def test_bad_targets_rejected(self):
        for value in ['', ' ', 'all', '*', 'a1', 'a1b2c', 'a1b2c34', 'zzzzzz', 'Tower']:
            with self.subTest(value=value), self.assertRaises(m.SafetyError):
                m.resolve_targets([value], [contact(A)])
    def test_unknown_or_duplicate_or_nonrepeater_rejected(self):
        for selectors, contacts in [(['ffffff'], [contact(A)]), (['a1b2c3', A], [contact(A)]), (['a1b2c3'], [contact(A, 3)])]:
            with self.subTest(selectors=selectors), self.assertRaises(m.SafetyError):
                m.resolve_targets(selectors, contacts)
    def test_allowlist_uses_full_keys(self):
        with self.assertRaises(m.SafetyError):
            m.resolve_targets(['a1b2c3'], [contact(A)], B)
        self.assertEqual(len(m.resolve_targets(['a1b2c3'], [contact(A)], A)), 1)
    def test_invalid_second_target_prevents_all_radio_commands(self):
        fake = FakeClient()
        with self.assertRaises(m.SafetyError):
            self.run_op(fake, selectors=['a1b2c3', 'ffffff'])
        self.assertFalse(any(x[0] in ('login', 'command') for x in fake.calls))
    def test_preview_has_no_radio_commands_or_journal(self):
        fake = FakeClient()
        output, code = self.run_op(fake, apply=False)
        self.assertEqual(code, 0)
        self.assertEqual(output['mode'], 'preview')
        self.assertFalse(any(x[0] in ('login', 'command') for x in fake.calls))
        self.assertEqual(list(self.state.glob('*.jsonl')), [])
    def test_verified_write_and_durable_before_record(self):
        fake = FakeClient(replies={(A, 'get int.thresh'): ['> 14', '> 0'], (A, 'set int.thresh 0'): ['OK']})
        output, code = self.run_op(fake)
        self.assertEqual(code, 0)
        self.assertEqual(output['results'][0]['status'], 'verified_config')
        records = [json.loads(line) for line in Path(output['audit_file']).read_text().splitlines()]
        intent = next(x for x in records if x['event'] == 'write_intent')
        self.assertEqual(intent['node']['before'], '14')
        self.assertEqual(intent['node']['public_key'], A)
        self.assertNotIn('FAKE_SECRET_8129', Path(output['audit_file']).read_text())
    def test_timeout_write_is_never_retried_and_can_verify(self):
        fake = FakeClient(replies={(A, 'get int.thresh'): ['> 14', '> 0'],
                                   (A, 'set int.thresh 0'): [m.ApiError('transport_error')]})
        output, code = self.run_op(fake)
        self.assertEqual(code, 0)
        self.assertEqual(output['results'][0]['status'], 'verified_config')
        self.assertEqual(fake.calls.count(('command', A, 'set int.thresh 0')), 1)
    def test_no_reply_write_gets_read_back_once_not_resent(self):
        fake = FakeClient(replies={(A, 'get int.thresh'): ['> 14', '> 0'],
                                   (A, 'set int.thresh 0'): [m.NO_REPLY]})
        output, code = self.run_op(fake)
        self.assertEqual(code, 0)
        self.assertEqual(fake.calls.count(('command', A, 'set int.thresh 0')), 1)
    def test_error_reply_is_rejected_and_batch_stops(self):
        fake = FakeClient(replies={(A, 'get int.thresh'): ['> 14'], (A, 'set int.thresh 0'): ['Err - no permission']})
        output, code = self.run_op(fake, selectors=['a1b2c3', 'd4e5f6'])
        self.assertEqual(code, 3)
        self.assertEqual([x['status'] for x in output['results']], ['rejected', 'skipped_after_failure'])
        self.assertNotIn(('login', B), fake.calls)
    def test_mismatch_never_claims_success(self):
        fake = FakeClient(replies={(A, 'get int.thresh'): ['> 14', '> 12'], (A, 'set int.thresh 0'): ['OK']})
        output, code = self.run_op(fake)
        self.assertEqual((code, output['results'][0]['status']), (3, 'verification_mismatch'))
    def test_missing_readback_is_unconfirmed(self):
        fake = FakeClient(replies={(A, 'get int.thresh'): ['> 14', m.NO_REPLY, m.NO_REPLY],
                                   (A, 'set int.thresh 0'): ['OK']})
        output, code = self.run_op(fake)
        self.assertEqual((code, output['results'][0]['status']), (3, 'unconfirmed'))
    def test_already_matching_no_write(self):
        fake = FakeClient(replies={(A, 'get int.thresh'): ['> 0.0']})
        output, code = self.run_op(fake)
        self.assertEqual(output['results'][0]['status'], 'unchanged')
        self.assertFalse(any(x[0] == 'command' and x[2].startswith('set ') for x in fake.calls))
    def test_login_failure_no_commands_or_retries(self):
        fake = FakeClient()
        fake.login_failure = True
        output, code = self.run_op(fake)
        self.assertEqual(code, 3)
        self.assertEqual(fake.calls.count(('login', A)), 1)
        self.assertFalse(any(x[0] == 'command' for x in fake.calls))
    def test_identity_mismatch_blocks_requested_command(self):
        fake = FakeClient(replies={(A, 'get public.key'): ['> ' + B]})
        output, code = self.run_op(fake)
        self.assertEqual(code, 3)
        self.assertNotIn(('command', A, 'set int.thresh 0'), fake.calls)
    def test_reboot_requires_flag_and_single_target(self):
        for selectors, flag in [(['a1b2c3'], False), (['a1b2c3', 'd4e5f6'], True)]:
            fake = FakeClient()
            with self.assertRaises(m.SafetyError):
                self.run_op(fake, 'reboot', selectors, disruptive=flag)
            self.assertFalse(any(x[0] in ('login', 'command') for x in fake.calls))
    def test_reboot_no_reply_unconfirmed_single_send(self):
        fake = FakeClient(replies={(A, 'reboot'): [m.NO_REPLY]})
        output, code = self.run_op(fake, 'reboot', disruptive=True)
        self.assertEqual((code, output['results'][0]['status']), (3, 'sent_unconfirmed'))
        self.assertEqual(fake.calls.count(('command', A, 'reboot')), 1)
    def test_reboot_error_rejected(self):
        fake = FakeClient(replies={(A, 'reboot'): ['Error: not permitted']})
        output, code = self.run_op(fake, 'reboot', disruptive=True)
        self.assertEqual((code, output['results'][0]['status']), (3, 'rejected'))
    def test_read_retry_is_bounded_and_success_does_not_crash(self):
        fake = FakeClient(replies={(A, 'ver'): [m.NO_REPLY, 'v1.test']})
        output, code = self.run_op(fake, 'ver')
        self.assertEqual(code, 0)
        self.assertEqual(fake.calls.count(('command', A, 'ver')), 2)
    def test_http_auth_error_not_retried(self):
        fake = FakeClient(replies={(A, 'ver'): [m.ApiError('http_error', 401)]})
        output, code = self.run_op(fake, 'ver')
        self.assertEqual(code, 3)
        self.assertEqual(fake.calls.count(('command', A, 'ver')), 1)
    def test_sensitive_unknown_and_injected_commands_blocked(self):
        for command in ['password secret', 'get guest.password', 'set prv.key abc', 'set bridge.secret abc', 'erase',
                        'set radio 1,2,3,4', 'set freq 915', 'int.thresh 0', 'ver\nreboot', 'reboot now', 'get name extra']:
            with self.subTest(command=command), self.assertRaises(m.SafetyError):
                m.classify(command)
    def test_numeric_validation_and_canonicalisation(self):
        for command in ['set int.thresh nan', 'set int.thresh -1', 'set int.thresh 1.5', 'set agc.reset.interval 17', 'set advert.interval 61']:
            with self.subTest(command=command), self.assertRaises(m.SafetyError):
                m.classify(command)
        self.assertEqual(m.classify('set int.thresh 1e1').command, 'set int.thresh 10')
    def test_exact_get_parsing_and_comparison(self):
        self.assertEqual(m.value_of('> 0\n'), '0')
        self.assertTrue(m.equivalent('int.thresh', '0.0', '0'))
        self.assertFalse(m.equivalent('int.thresh', '0.001', '0'))
        for reply in ['OK', 'Unknown command', '> a\nb', '']:
            with self.assertRaises(m.SafetyError):
                m.value_of(reply)
    def test_env_literal_no_expansion_and_duplicates_fail(self):
        values = m.parse_env("RT_PASS='abc# $HOME $(echo nope)'\nOTHER=hello\n")
        self.assertEqual(values['RT_PASS'], 'abc# $HOME $(echo nope)')
        with self.assertRaises(m.SafetyError):
            m.parse_env('RT_PASS=a\nRT_PASS=b')
    def test_env_permissions_and_no_environment_override(self):
        path = Path(self.temp.name) / '.env'
        path.write_text('RT_BASE=https://radio.invalid\nRT_USER=test\nRT_PASS=FAKE\n')
        path.chmod(0o600)
        with patch.dict(os.environ, {'RT_BASE': 'http://evil.invalid'}):
            self.assertEqual(m.Config.load(path).base, 'https://radio.invalid')
        if os.name == 'posix':
            path.chmod(0o644)
            with self.assertRaises(m.SafetyError):
                m.Config.load(path)
    def test_https_and_loopback_only(self):
        for base in ['http://192.168.1.1', 'http://100.64.0.1', 'http://localhost', 'https://u:p@host', 'https://host/path', 'https://host/?q=x']:
            with self.subTest(base=base), self.assertRaises(m.SafetyError):
                m.validate_base(base, True)
        self.assertEqual(m.validate_base('http://127.0.0.1:8081', True), 'http://127.0.0.1:8081')
        self.assertEqual(m.validate_base('https://HOST:443/'), 'https://host')
    def test_tls_verification_and_redirects_disabled(self):
        client = m.Client(self.cfg)
        handler = next(h for h in client.opener.handlers if isinstance(h, m.urllib.request.HTTPSHandler))
        self.assertEqual(handler._context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(handler._context.check_hostname)
        self.assertIsNone(m.NoRedirect().redirect_request(None, None, 302, None, {}, 'https://evil.invalid'))
    def test_redaction_and_per_node_password_precedence(self):
        values = {'RT_USER': 'user', 'RT_PASS': 'WEB_SECRET', 'MESHCORE_REPEATER_PASSWORD': 'SHARED_SECRET',
                  'MESHCORE_REPEATER_PASSWORD_A1B2C3': 'PREFIX_SECRET',
                  'MESHCORE_REPEATER_PASSWORD_' + A.upper(): 'FULL_SECRET'}
        cfg = m.Config('https://radio.invalid', values)
        self.assertEqual(cfg.password_for(A, [contact(A), contact(C)]), 'FULL_SECRET')
        del values['MESHCORE_REPEATER_PASSWORD_' + A.upper()]
        with self.assertRaises(m.SafetyError):
            cfg.password_for(A, [contact(A), contact(C)])
        self.assertEqual(cfg.password_for(A, [contact(A)]), 'PREFIX_SECRET')
        self.assertEqual(cfg.redact('WEB_SECRET PREFIX_SECRET SHARED_SECRET'), '[REDACTED] [REDACTED] [REDACTED]')
    def test_local_lock_prevents_second_instance(self):
        with m.server_lock(self.state, 'https://radio.invalid'):
            with self.assertRaises(m.SafetyError):
                with m.server_lock(self.state, 'https://radio.invalid:8443'):
                    pass
    def test_pagination_scans_later_contacts(self):
        client = m.Client(self.cfg)
        page = [contact(f'{i:064x}') for i in range(1000)]
        with patch.object(client, 'request', side_effect=[page, [contact(A), contact(C)]]) as req:
            contacts = client.contacts()
            self.assertEqual(len(contacts), 1002)
            self.assertIn('offset=1000', req.call_args.args[1])
            with self.assertRaises(m.SafetyError):
                m.resolve_targets(['a1b2c3'], contacts)
    def test_incomplete_or_duplicate_inventory_fails_closed(self):
        client = m.Client(self.cfg)
        for page in [[contact(A), contact(A)], [{'public_key': 'bad'}], {'contacts': []}]:
            with self.subTest(page=page), patch.object(client, 'request', return_value=page), self.assertRaises(m.SafetyError):
                client.contacts()
    def test_intent_is_durable_before_send(self):
        fake = FakeClient(replies={(A, 'get int.thresh'): ['> 14', '> 0'], (A, 'set int.thresh 0'): ['OK']})
        original = fake.command_once
        def inspect(pk, command):
            if command.startswith('set '):
                logs = list(self.state.glob('*.jsonl'))
                self.assertEqual(len(logs), 1)
                records = [json.loads(x) for x in logs[0].read_text().splitlines()]
                self.assertEqual(records[-1]['event'], 'write_intent')
                self.assertEqual(records[-1]['node']['before'], '14')
            return original(pk, command)
        fake.command_once = inspect
        self.run_op(fake)
    def test_missing_one_password_prevents_all_logins(self):
        self.cfg.values = {'MESHCORE_REPEATER_PASSWORD_A1B2C3': 'FAKE_ONLY_A'}
        fake = FakeClient()
        with self.assertRaises(m.SafetyError):
            self.run_op(fake, selectors=['a1b2c3', 'd4e5f6'])
        self.assertFalse(any(x[0] == 'login' for x in fake.calls))

if __name__ == '__main__':
    unittest.main()
