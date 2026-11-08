"""Identity-reply compatibility tests using synthetic keys only; no network."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_repeater_cmd as fixture


class IdentityReplyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "state"
        self.config = fixture.m.Config(
            "https://radio.invalid", {"MESHCORE_REPEATER_PASSWORD": "SYNTHETIC_TEST_ONLY"}
        )
        sleeper = patch.object(fixture.m.time, "sleep", lambda _: None)
        sleeper.start()
        self.addCleanup(sleeper.stop)

    def run_read(self, reply, command="ver"):
        identity_replies = [reply, reply] if command == "get public.key" else [reply]
        fake = fixture.FakeClient(
            contacts=[fixture.contact(fixture.A)],
            replies={(fixture.A, "get public.key"): identity_replies},
        )
        result, code = fixture.m.operate(
            fake, self.config, [fixture.A], fixture.m.classify(command),
            True, False, self.state,
        )
        return fake, result, code

    def test_bare_uppercase_full_key_allows_firmware_read(self):
        fake, result, code = self.run_read(fixture.A.upper())
        self.assertEqual(code, 0)
        self.assertEqual(result["results"][0]["status"], "read_ok")
        self.assertEqual(result["results"][0]["response"], "v1.test (Build: offline)")
        self.assertEqual(fake.calls.count(("command", fixture.A, "ver")), 1)
        records = [json.loads(line) for line in Path(result["audit_file"]).read_text().splitlines()]
        self.assertFalse(any(row["event"] == "write_intent" for row in records))
        self.assertFalse(any(call[0] == "command" and call[2].startswith("set ") for call in fake.calls))


    def test_explicit_public_key_read_accepts_bare_full_key(self):
        fake, result, code = self.run_read(fixture.A.upper(), "get public.key")
        self.assertEqual(code, 0)
        self.assertEqual(result["results"][0]["status"], "read_ok")
        self.assertEqual(result["results"][0]["response"], fixture.A.upper())
        self.assertEqual(fake.calls.count(("command", fixture.A, "get public.key")), 2)

    def test_only_complete_hex_key_reply_forms_are_accepted(self):
        for reply in (fixture.A, fixture.A.upper(), "> " + fixture.A,
                      "> " + fixture.A.upper() + "\r\n", fixture.A + "\n"):
            with self.subTest(reply=reply):
                self.assertEqual(fixture.m.public_key_of(reply), fixture.A)

    def test_malformed_identity_reply_never_reaches_requested_command(self):
        for reply in ("OK", "prefix " + fixture.A, fixture.A + " extra", fixture.A[:6],
                      fixture.A[:-1], fixture.A + "0", "g" * 64, fixture.A + "\nignored",
                      fixture.A + "\n\r\n", fixture.A + "\n\n", " " + fixture.A,
                      fixture.A + " ", fixture.A + "\x00", ">> " + fixture.A):
            with self.subTest(reply=reply):
                fake, result, code = self.run_read(reply)
                self.assertEqual(code, 3)
                self.assertEqual(result["results"][0]["status"], "failed")
                self.assertNotIn(("command", fixture.A, "ver"), fake.calls)

    def test_different_valid_bare_key_still_blocks_requested_command(self):
        fake, result, code = self.run_read(fixture.B.upper())
        self.assertEqual(code, 3)
        self.assertEqual(result["results"][0]["error"],
                         "Remote public key did not match the resolved target; aborting.")
        self.assertNotIn(("command", fixture.A, "ver"), fake.calls)

    def test_generic_setting_parser_still_rejects_bare_values(self):
        for value in ("0", fixture.A):
            with self.subTest(value=value), self.assertRaises(fixture.m.SafetyError):
                fixture.m.value_of(value)


if __name__ == "__main__":
    unittest.main()
