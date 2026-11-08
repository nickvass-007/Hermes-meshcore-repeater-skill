#!/usr/bin/env python3
"""MeshCore RemoteTerm operator, v2.0.1. Python 3.10+, standard library only.
No configuration write is retried. Network access occurs only from main().
"""
from __future__ import annotations
import argparse
import base64
import contextlib
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import ssl
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

VERSION = "2.0.1"
DEFAULT_ENV = Path.home() / ".hermes/secrets/meshcore/.env"
DEFAULT_STATE = Path.home() / ".hermes/state/meshcore"
NO_REPLY = "(no response - command may have been processed)"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SELECTOR = re.compile(r"(?:[0-9a-f]{6}|[0-9a-f]{64})\Z")
# Conservative local bounds, not claims about every board's capabilities.
NUMBERS = {
    "int.thresh": (0, 255, True), "af": (0, 1000, False),
    "dutycycle": (1, 100, False), "txdelay": (0, 2, False),
    "direct.txdelay": (0, 2, False), "rxdelay": (0, 100, False),
    "agc.reset.interval": (0, 1020, True), "multi.acks": (0, 1, True),
    "lat": (-90, 90, False), "lon": (-180, 180, False),
    "flood.max": (0, 64, True), "flood.max.unscoped": (0, 64, True),
    "flood.max.advert": (0, 64, True), "path.hash.mode": (0, 2, True),
    "tx": (0, 30, True), "advert.interval": (0, 240, True),
    "flood.advert.interval": (0, 168, True),
}
ENUMS = {"cad": {"on", "off"}, "repeat": {"on", "off"},
         "loop.detect": {"off", "minimal", "moderate", "strict"}}
TEXT_KEYS = {"name", "owner.info"}
GET_KEYS = set(NUMBERS) | set(ENUMS) | TEXT_KEYS | {"public.key", "freq", "radio", "role", "firmware.ver", "bootloader.ver"}
SINGLE_TARGET_KEYS = {"repeat", "tx", "path.hash.mode", "flood.max", "flood.max.unscoped", "flood.max.advert", "loop.detect"}
ACTIONS = {"reboot", "poweroff", "shutdown", "clkreboot", "start ota"}
READ_COMMANDS = {"ver", "board", "clock", "neighbors"}

class SafetyError(Exception):
    pass

class ApiError(Exception):
    def __init__(self, category, status=None):
        self.category, self.status = category, status
        super().__init__(category + (f" (HTTP {status})" if status else ""))


def protected_file(path: Path):
    """Read an owned regular file without following its final symlink (POSIX)."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        raise SafetyError("Cannot open credential file; check its path and permissions.") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise SafetyError("Credential file must be a regular file.")
        if os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise SafetyError("Credential file must belong to this user with mode 0600 or 0400.")
        with os.fdopen(fd, "r", encoding="utf-8-sig") as handle:
            fd = None
            content = handle.read(65537)
        if len(content) > 65536:
            raise SafetyError("Credential file is too large.")
        return content
    finally:
        if fd is not None:
            os.close(fd)


def parse_env(content: str):
    """Literal KEY=value subset: no interpolation, shell execution or escape expansion."""
    values = {}
    for number, raw in enumerate(content.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise SafetyError(f"Invalid .env syntax at line {number}; contents suppressed.")
        if key in values:
            raise SafetyError(f"Duplicate .env key at line {number}; contents suppressed.")
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise SafetyError(f"Unclosed .env quote at line {number}; contents suppressed.")
            value = value[1:-1]
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise SafetyError(f"Control character in .env line {number}; contents suppressed.")
        values[key] = value
    return values


def validate_base(base, allow_loopback=False):
    try:
        p = urllib.parse.urlsplit(base)
        port = p.port
    except ValueError:
        raise SafetyError("Invalid RT_BASE URL.") from None
    if (not p.hostname or p.username is not None or p.password is not None or p.query or p.fragment
            or p.path not in ("", "/") or any(c.isspace() for c in base)):
        raise SafetyError("RT_BASE must be an origin URL without credentials, path, query or fragment.")
    if p.scheme != "https":
        try:
            loopback = ipaddress.ip_address(p.hostname).is_loopback
        except ValueError:
            loopback = False
        if not (p.scheme == "http" and allow_loopback and loopback):
            raise SafetyError("HTTPS is required. HTTP is allowed only for explicitly enabled literal loopback addresses.")
    host = p.hostname.lower()
    if ":" in host:
        host = "[" + host + "]"
    default_port = 443 if p.scheme == "https" else 80
    return f"{p.scheme}://{host}" + (f":{port}" if port and port != default_port else "")


@dataclass
class Config:
    base: str
    values: dict
    ca_file: str | None = None

    @classmethod
    def load(cls, path):
        path = Path(path).expanduser()
        values = parse_env(protected_file(path))
        base = validate_base(values.get("RT_BASE", ""), values.get("RT_ALLOW_HTTP_LOOPBACK") == "1")
        user, password = values.get("RT_USER", ""), values.get("RT_PASS", "")
        if bool(user) != bool(password) or ":" in user:
            raise SafetyError("Set RT_USER and RT_PASS together; RT_USER cannot contain a colon.")
        ca = values.get("RT_CA_FILE") or None
        if ca:
            ca_path = Path(ca).expanduser()
            if not ca_path.is_absolute():
                ca_path = path.absolute().parent / ca_path
            ca = str(ca_path)
        allowed = values.get("MESHCORE_ALLOWED_KEYS", "")
        if allowed and any(not HEX64.fullmatch(k.strip().lower()) for k in allowed.split(",")):
            raise SafetyError("MESHCORE_ALLOWED_KEYS must contain comma-separated full 64-character public keys.")
        return cls(base, values, ca)

    def password_for(self, pk, contacts):
        full = self.values.get("MESHCORE_REPEATER_PASSWORD_" + pk.upper())
        prefix = pk[:6]
        prefix_secret = self.values.get("MESHCORE_REPEATER_PASSWORD_" + prefix.upper())
        if full:
            return full
        if prefix_secret:
            if sum(c["public_key"].startswith(prefix) for c in contacts) != 1:
                raise SafetyError("A per-prefix password is ambiguous. Configure the full-public-key password entry.")
            return prefix_secret
        return self.values.get("MESHCORE_REPEATER_PASSWORD", "")

    def redact(self, value):
        if isinstance(value, dict):
            return {k: self.redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.redact(v) for v in value]
        if not isinstance(value, str):
            return value
        secrets = [v for k, v in self.values.items() if v and ("PASS" in k or "SECRET" in k or "TOKEN" in k)]
        if self.values.get("RT_USER"):
            secrets.append(base64.b64encode((self.values["RT_USER"] + ":" + self.values["RT_PASS"]).encode()).decode())
        for secret in sorted(set(secrets), key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
        return "".join(c if c.isprintable() or c in "\n\t" else "?" for c in value)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, config):
        self.config = config
        try:
            context = ssl.create_default_context(cafile=config.ca_file)
        except (OSError, ssl.SSLError):
            raise SafetyError("Cannot load RT_CA_FILE; TLS verification remains required.") from None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                                  urllib.request.HTTPSHandler(context=context))
        self.next_post = 0.0

    def request(self, method, path, body=None):
        if method == "POST":
            time.sleep(max(0, self.next_post - time.monotonic()))
        headers = {"Accept": "application/json"}
        if self.config.values.get("RT_USER"):
            token = base64.b64encode((self.config.values["RT_USER"] + ":" + self.config.values["RT_PASS"]).encode()).decode()
            headers["Authorization"] = "Basic " + token
        data = None if body is None else json.dumps(body).encode()
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.config.base + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=60 if method == "POST" else 20) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ApiError("oversized_response")
                try:
                    return json.loads(raw)
                except (ValueError, UnicodeError):
                    raise ApiError("invalid_json") from None
        except urllib.error.HTTPError as e:
            # Never echo untrusted error bodies, credentials or redirect destinations.
            raise ApiError("http_error", e.code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ApiError("transport_error") from None
        finally:
            if method == "POST":
                self.next_post = time.monotonic() + 4.0

    def health(self):
        result = self.request("GET", "/api/health")
        if not isinstance(result, dict) or result.get("radio_connected") is not True:
            raise SafetyError("Radio is not connected, or health response is incompatible.")

    def contacts(self):
        all_contacts, seen = [], set()
        for offset in range(0, 100_000, 1000):
            page = self.request("GET", f"/api/contacts?limit=1000&offset={offset}")
            if not isinstance(page, list) or len(page) > 1000:
                raise SafetyError("Incompatible contacts response.")
            for entry in page:
                if not isinstance(entry, dict):
                    raise SafetyError("Malformed contact; refusing incomplete target resolution.")
                pk = entry.get("public_key", "")
                if not isinstance(pk, str) or not HEX64.fullmatch(pk.lower()):
                    raise SafetyError("Invalid contact public key; refusing incomplete target resolution.")
                pk = pk.lower()
                if pk in seen:
                    raise SafetyError("Duplicate/pagination-shifted contact key; reload the inventory before proceeding.")
                seen.add(pk)
                all_contacts.append({**entry, "public_key": pk})
            if len(page) < 1000:
                return all_contacts
        raise SafetyError("Contact pagination limit reached; refusing a partial inventory.")

    def login(self, pk, password):
        # One API call. RemoteTerm may itself retry once via flood routing.
        result = self.request("POST", f"/api/contacts/{pk}/repeater/login", {"password": password})
        if not isinstance(result, dict) or result.get("authenticated") is not True:
            raise SafetyError("Login was not confirmed; no command was sent. No client-side login retry.")

    def command_once(self, pk, command):
        result = self.request("POST", f"/api/contacts/{pk}/command", {"command": command})
        if not isinstance(result, dict) or not isinstance(result.get("response"), str):
            raise ApiError("incompatible_command_response")
        return result["response"]


def resolve_targets(selectors, contacts, allowed=""):
    if not selectors:
        raise SafetyError("At least one explicit target is required.")
    permitted = {k.strip().lower() for k in allowed.split(",") if k.strip()}
    targets, selected = [], set()
    for raw in selectors:
        selector = raw.strip().lower()
        if not SELECTOR.fullmatch(selector):
            raise SafetyError("Targets must be exactly six hex characters, or a full 64-character public key. Names/all/* are disabled.")
        matches = [c for c in contacts if c["public_key"].startswith(selector)]
        if len(matches) != 1:
            raise SafetyError(f"Target {selector} matches {len(matches)} contacts; require exactly one. Use a full public key for a collision.")
        node = matches[0]
        if node.get("type") != 2:
            raise SafetyError(f"Target {selector} is not a repeater.")
        if permitted and node["public_key"] not in permitted:
            raise SafetyError(f"Target {selector} is outside MESHCORE_ALLOWED_KEYS.")
        if node["public_key"] in selected:
            raise SafetyError("Duplicate target selectors; provide each node once.")
        targets.append(node)
        selected.add(node["public_key"])
    if len(targets) > 10:
        raise SafetyError("Batch limit is ten explicitly selected repeaters.")
    return targets


@dataclass(frozen=True)
class Operation:
    command: str
    kind: str
    key: str = ""
    value: str = ""
    disruptive: bool = False


def numeric(value):
    try:
        result = Decimal(value)
        if not result.is_finite():
            raise InvalidOperation
        return result
    except InvalidOperation:
        raise SafetyError("Expected a finite numeric parameter.") from None


def classify(raw):
    if any(not c.isprintable() for c in raw) or len(raw.encode("utf-8")) > 120:
        raise SafetyError("Command must be a single printable line of at most 120 UTF-8 bytes.")
    command = raw.strip()
    if not command:
        raise SafetyError("Empty command.")
    if command in ACTIONS:
        return Operation(command, "action", disruptive=True)
    if command in READ_COMMANDS:
        return Operation(command, "read")
    if command.startswith("get ") and command[4:] in GET_KEYS:
        return Operation(command, "read", key=command[4:])
    # Explicit set is required; shorthand cannot silently turn a query into a write.
    match = re.fullmatch(r"set ([a-z.]+) (.+)", command)
    if not match:
        raise SafetyError("Unsupported command. Only documented reads, approved set parameters and explicit actions are allowed.")
    key, value = match.groups()
    if key in NUMBERS:
        n = numeric(value)
        low, high, integer = NUMBERS[key]
        if not low <= n <= high or (integer and n != n.to_integral_value()):
            raise SafetyError("Parameter outside the conservative supported range.")
        if key == "agc.reset.interval" and n % 4:
            raise SafetyError("agc.reset.interval must be a multiple of four seconds.")
        if key == "advert.interval" and (n % 2 or 0 < n < 60):
            raise SafetyError("advert.interval must be 0, or an even number of minutes from 60 to 240.")
        if key == "flood.advert.interval" and 0 < n < 3:
            raise SafetyError("flood.advert.interval must be 0, or 3 to 168 hours.")
        # Canonical decimal avoids firmware atoi/atof differences with exponent notation.
        value = format(n, "f")
        if integer:
            value = str(int(n))
    elif key in ENUMS:
        if value not in ENUMS[key]:
            raise SafetyError("Unsupported enumeration value.")
    elif key in TEXT_KEYS:
        limit = 31 if key == "name" else 80
        if value != value.strip() or len(value.encode("utf-8")) > limit:
            raise SafetyError("Text parameter is too long or has surrounding whitespace.")
    else:
        raise SafetyError("Unsupported set parameter. Credential, key, frequency, radio and arbitrary commands are intentionally blocked.")
    return Operation(f"set {key} {value}", "set", key, value, key in SINGLE_TARGET_KEYS)


def is_error(response):
    text = response.strip().lower().lstrip("(").strip()
    return text.startswith(("err", "unknown", "invalid", "denied", "unauthor", "not allowed", "failed", "failure", "can't", "cannot", "unsupported"))


def value_of(response):
    if not isinstance(response, str) or not response.strip().startswith("> "):
        raise SafetyError("Unexpected get response format; refusing to infer a setting.")
    value = response.strip()[2:].strip()
    if not value or "\n" in value or "\r" in value:
        raise SafetyError("Empty/multiline get response; refusing to infer a setting.")
    return value


def public_key_of(response):
    """Accept only a complete hex identity, optionally using the CLI '> ' prefix."""
    if not isinstance(response, str):
        raise SafetyError("Unexpected public-key response; require a full 64-character hex key.")
    # Permit one transport line ending, not arbitrary whitespace or extra lines.
    value = response[:-2] if response.endswith("\r\n") else response.removesuffix("\n")
    if value.startswith("> "):
        value = value[2:]
    if not HEX64.fullmatch(value.lower()):
        raise SafetyError("Unexpected public-key response; require a full 64-character hex key.")
    return value.lower()


def equivalent(key, actual, expected):
    if key in NUMBERS:
        if key == "dutycycle":
            actual = actual.removesuffix("%").strip()
        try:
            return numeric(actual) == numeric(expected)
        except SafetyError:
            return False
    return actual == expected


def read_command(client, pk, command):
    for attempt in range(2):
        try:
            response = client.command_once(pk, command)
        except ApiError as e:
            # HTTP errors and malformed replies are not retried. Only uncertain transport reads.
            if e.category != "transport_error" or attempt == 1:
                raise
            continue
        if is_error(response):
            raise SafetyError("Read was rejected by the repeater.")
        if response.strip() and response.strip() != NO_REPLY:
            return response
    raise SafetyError("No read response after two attempts.")


def secure_directory(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or (os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
        raise SafetyError("State directory must be private and owned by this user (0700 on POSIX).")


@contextlib.contextmanager
def server_lock(state, base):
    secure_directory(state)
    # Host-level lock also covers alternate URL ports, paths and HTTP/HTTPS for the same host.
    host = urllib.parse.urlsplit(base).hostname.lower()
    path = state / (hashlib.sha256(host.encode()).hexdigest() + ".lock")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or (os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
            raise SafetyError("Lock file is not private or is not a regular file.")
        if os.name == "nt":
            import msvcrt
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"0")
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError:
                raise SafetyError("Another local operation holds the radio lock.") from None
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise SafetyError("Another local operation holds the radio lock.") from None
        yield
    finally:
        os.close(fd)


class Journal:
    def __init__(self, state, config):
        self.config = config
        self.run_id = uuid.uuid4().hex
        self.path = state / (self.run_id + ".jsonl")
        self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)

    def record(self, event, **data):
        record = self.config.redact({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                     "run_id": self.run_id, "event": event, **data})
        payload = (json.dumps(record, ensure_ascii=True) + "\n").encode()
        while payload:
            count = os.write(self.fd, payload)
            if count <= 0:
                raise OSError("journal write failed")
            payload = payload[count:]
        os.fsync(self.fd)

    def close(self):
        os.close(self.fd)


def execute_node(client, node, password, operation, journal):
    pk = node["public_key"]
    result = {"public_key": pk, "prefix": pk[:6], "name": node.get("name", ""), "status": "failed", "write_sends": 0}
    client.health()
    client.login(pk, password)
    # Confirm remote CLI access and full identity before executing the requested operation.
    actual_key = public_key_of(read_command(client, pk, "get public.key"))
    if actual_key != pk:
        raise SafetyError("Remote public key did not match the resolved target; aborting.")
    if operation.kind == "read":
        response = read_command(client, pk, operation.command)
        if operation.key == "public.key":
            public_key_of(response)
        elif operation.key:
            value_of(response)
        result.update(status="read_ok", response=response)
        return result
    result["firmware"] = read_command(client, pk, "ver")
    if operation.kind == "set":
        before = value_of(read_command(client, pk, "get " + operation.key))
        result["before"] = before
        result["expected"] = operation.value
        if equivalent(operation.key, before, operation.value):
            result.update(status="unchanged", after=before)
            return result
    # This durable record precedes any configuration/action POST.
    journal.record("write_intent", command=operation.command, node=result,
                   recovery="Review before value; no automatic rollback or resend.")
    client.health()
    result["write_sends"] = 1
    try:
        response = client.command_once(pk, operation.command)
        if is_error(response):
            result.update(status="rejected", response=response)
            return result
        result["write_reply"] = response
    except ApiError as error:
        result["write_error"] = str(error)
        if error.status in (401, 403):
            result["status"] = "unconfirmed"
            return result
    if operation.kind == "action":
        result["status"] = "sent_unconfirmed"
        return result
    try:
        after = value_of(read_command(client, pk, "get " + operation.key))
        result["after"] = after
        result["status"] = "verified_config" if equivalent(operation.key, after, operation.value) else "verification_mismatch"
    except (ApiError, SafetyError) as error:
        result.update(status="unconfirmed", verification_error=str(error))
    if operation.key == "tx":
        result["note"] = "Configured transmit power only; firmware may require a separately authorised reboot. RF output is not measured."
    return result


def operate(client, config, selectors, operation, apply, allow_disruptive, state):
    with server_lock(state, config.base):
        client.health()
        contacts = client.contacts()
        targets = resolve_targets(selectors, contacts, config.values.get("MESHCORE_ALLOWED_KEYS", ""))
        if operation.disruptive and len(targets) != 1:
            raise SafetyError("This disruptive operation is limited to one explicitly selected repeater.")
        plan = {"version": VERSION, "mode": "apply" if apply else "preview", "command": operation.command,
                "disruptive": operation.disruptive,
                "targets": [{"prefix": c["public_key"][:6], "public_key": c["public_key"], "name": c.get("name", "")} for c in targets]}
        if not apply:
            return plan, 0
        if operation.disruptive and not allow_disruptive:
            raise SafetyError("Disruptive operation requires --allow-disruptive and an explicit user request covering its consequences.")
        passwords = [config.password_for(c["public_key"], contacts) for c in targets]
        if not all(passwords):
            raise SafetyError("A repeater password must be configured for every selected node before execution.")
        journal = Journal(state, config)
        results = []
        try:
            journal.record("plan", **plan)
            for index, (node, password) in enumerate(zip(targets, passwords)):
                try:
                    result = execute_node(client, node, password, operation, journal)
                except (ApiError, SafetyError) as error:
                    result = {"public_key": node["public_key"], "status": "failed", "error": str(error)}
                journal.record("result", **result)
                results.append(result)
                if result["status"] not in {"read_ok", "unchanged", "verified_config"}:
                    for skipped in targets[index + 1:]:
                        item = {"public_key": skipped["public_key"], "status": "skipped_after_failure"}
                        results.append(item)
                        journal.record("result", **item)
                    break
                if index < len(targets) - 1:
                    time.sleep(4)
            code = 0 if all(r["status"] in {"read_ok", "unchanged", "verified_config"} for r in results) else 3
            journal.record("complete", exit_code=code)
            return {**plan, "run_id": journal.run_id, "audit_file": str(journal.path), "results": results}, code
        finally:
            journal.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(DEFAULT_ENV))
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE))
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("list", help="List repeaters and prefix collisions without radio commands")
    run = sub.add_parser("run", help="Preview an explicit operation; --apply executes it")
    run.add_argument("--target", action="append", required=True, help="Repeat for multiple six-hex prefixes (or full public keys)")
    run.add_argument("--command", required=True)
    run.add_argument("--apply", action="store_true")
    run.add_argument("--allow-disruptive", action="store_true")
    args = parser.parse_args(argv)
    config = None
    try:
        # Validate commands before constructing a network client.
        operation = classify(args.command) if args.operation == "run" else None
        config = Config.load(args.env_file)
        client = Client(config)
        if args.operation == "list":
            contacts = client.contacts()
            output = {"repeaters": [{"prefix": c["public_key"][:6], "public_key": c["public_key"],
                       "name": c.get("name", ""), "favorite": c.get("favorite", False),
                       "prefix_unique": sum(x["public_key"].startswith(c["public_key"][:6]) for x in contacts) == 1}
                      for c in contacts if c.get("type") == 2]}
            code = 0
        else:
            output, code = operate(client, config, args.target, operation, args.apply,
                                   args.allow_disruptive, Path(args.state_dir).expanduser())
        print(json.dumps(config.redact(output), indent=2, ensure_ascii=True))
        return code
    except (SafetyError, ApiError) as error:
        output = {"status": "aborted", "error": str(error)}
        print(json.dumps(config.redact(output) if config else output, ensure_ascii=True))
        return 2
    except (OSError, ValueError):
        print(json.dumps({"status": "aborted", "error": "Local I/O or configuration failure; details suppressed. Inspect the audit before repeating any operation."}))
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted", "error": "Operation interrupted. Inspect the durable audit and read back state; never blindly resend a write or action."}))
        return 130

if __name__ == "__main__":
    sys.exit(main())
