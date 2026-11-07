# Installation and operating notes

## Contents
1. Install
2. Configure the local .env
3. Examples
4. Supported commands
5. Validation and recovery
6. Sources and compatibility

## Install

This package targets Hermes on your operator computer, not the radio host unless that is where Hermes runs. Use a Python 3.10+ environment. Place `SKILL.md`, `scripts/repeater_cmd.py`, `references/setup.md` and `tests/test_repeater_cmd.py` inside your Hermes skills directory under `meshcore-repeater-command`. The usual directory is `~/.hermes/skills/meshcore-repeater-command`; if your Hermes installation uses a custom home, use its actual skills root. Back up an existing installation before replacing its code; retain credentials outside the skill folder.

Run the bundled offline tests before connecting. Do not install dependencies or run a sample configuration change as part of installation. No real credentials are included.

## Configure the local .env

Recommended path: `~/.hermes/secrets/meshcore/.env`. Create its containing directory privately, then create/edit the file locally using a trusted editor. Do not paste credentials into the assistant conversation.

On Linux/macOS, the directory should be `0700` and the file `0600` or `0400`, owned by the operator. The script rejects an overly permissive credential file. On Windows, restrict the directory/file ACL to your own user and required system administrators; Python's standard-library mode bits cannot validate Windows ACLs. Do not use `chmod` as a Windows ACL substitute. Keep credentials out of cloud-sync folders, source control, backups without encryption, and shared skill packages.

A copyable template is bundled as `references/meshcore.env.example`. Use the following keys (dummy values only):

```dotenv
RT_BASE=https://remoteterm.example.internal:8081
RT_USER=replace-locally
RT_PASS='replace-locally'
MESHCORE_REPEATER_PASSWORD='replace-locally'
# For a self-signed server, explicitly trust its certificate/CA after checking its fingerprint out of band.
# The hostname in RT_BASE must also match the certificate SAN.
RT_CA_FILE=/absolute/path/to/trusted-remoteterm-ca.pem
# Optional: restrict all explicitly selected operations to trusted full public keys.
# MESHCORE_ALLOWED_KEYS=<64-hex-key>,<another-64-hex-key>
# Optional per-node passwords; these take precedence over the shared repeater password:
# MESHCORE_REPEATER_PASSWORD_A1B2C3='node-specific-secret'
# MESHCORE_REPEATER_PASSWORD_<FULL_64_HEX_PUBLIC_KEY_IN_UPPERCASE>='node-specific-secret'
```

Remove `RT_CA_FILE` if the server uses a certificate trusted by the normal OS/Python trust store. A private CA or self-signed certificate does not justify disabling certificate verification. If RemoteTerm has no HTTP Basic auth, omit both RT_USER and RT_PASS; still restrict network access. The two passwords serve different purposes: RT_PASS authenticates to the web server, MESHCORE_REPEATER_PASSWORD authenticates to the repeater.

All configuration comes from the explicitly selected file, not inherited process environment variables. This prevents unexpected environment overrides. Additional unrelated KEY=value entries are tolerated, but this is a deliberately simple .env parser: one entry per line, optional matching outer quotes, no multiline values, no interpolation, no shell execution and no escape expansion. Comments must be on their own lines; an inline `#` is part of the value. Values inside quotes are preserved literally. Prefer a dedicated file.

Per-node suffixes are uppercase. A full-key password entry wins over a prefix entry, then the shared default. If a prefix password could refer to more than one known contact, execution stops even when the target is specified by full key; set a full-key password entry instead. The skill never edits these credentials or the allowlist.

Optional loopback-only HTTP for a secured local tunnel:
```dotenv
RT_BASE=http://127.0.0.1:8081
RT_ALLOW_HTTP_LOOPBACK=1
```
Only literal loopback IPs qualify, not LAN addresses, tailnet addresses or `localhost`. The tunnel's remote transport must itself be authenticated/encrypted. No proxy environment variables or redirects are honoured. HTTPS remains the recommended configuration.

## Examples

Use your actual script path and actual known prefixes; sample prefixes do not designate any device.

```sh
python ~/.hermes/skills/meshcore-repeater-command/scripts/repeater_cmd.py list
python ~/.hermes/skills/meshcore-repeater-command/scripts/repeater_cmd.py run --target a1b2c3 --command "ver"
python ~/.hermes/skills/meshcore-repeater-command/scripts/repeater_cmd.py run --target a1b2c3 --command "ver" --apply
python ~/.hermes/skills/meshcore-repeater-command/scripts/repeater_cmd.py run --target a1b2c3 --target d4e5f6 --command "set int.thresh 0"
```

For a separately previewed operation, execute using the full public keys printed in that preview and add `--apply`. This pins the identity if the contacts database changes between calls. A direct apply invocation accepts a unique six-character prefix and resolves it once before sending to the full key.

Global options precede the subcommand:
```sh
python /PATH/TO/SKILL/scripts/repeater_cmd.py --env-file /secure/path/.env run --target a1b2c3 --command "get int.thresh" --apply
```

A six-character hex prefix is 24 bits/three bytes. Uniqueness is checked against every contact fetched from this RemoteTerm, not the entire global mesh. New or unknown nodes and intentional prefix collisions exist; establish trusted full keys for nodes you own. The script checks returned remote identity before the requested operation, but still depends on a trusted RemoteTerm server and firmware.

Natural-language examples for Hermes:
- “Show the firmware on a1b2c3.”
- “Preview setting int.thresh to 0 on a1b2c3 and d4e5f6.”
- “Set int.thresh to 0 on a1b2c3 and d4e5f6, then verify both.”
- “Reboot a1b2c3 once; I accept the temporary outage. Report it as unconfirmed until there is independent evidence.”

## Supported commands

Read: `ver`, `board`, `clock`, `neighbors`; `get` for all supported set keys plus `public.key`, `freq`, `radio`, `role`, `firmware.ver`, `bootloader.ver`. Support still depends on target firmware. Unknown commands are rejected, not passed through.

Set parameters:
- Numeric: `int.thresh`, `af`, `dutycycle`, `txdelay`, `direct.txdelay`, `rxdelay`, `agc.reset.interval`, `multi.acks`, `lat`, `lon`, `flood.max`, `flood.max.unscoped`, `flood.max.advert`, `path.hash.mode`, `tx`, `advert.interval`, `flood.advert.interval`.
- Enumerated: `cad`, `repeat`, `loop.detect`.
- Text: `name` (31 UTF-8 bytes maximum), `owner.info` (80 UTF-8 bytes maximum).

Conservative local ranges are defined in `NUMBERS` in the script. They are input safeguards, not a declaration of board support, safe RF settings or legal operating limits. In particular, select transmit power/duty cycle according to your hardware, antenna and local rules; the script cannot determine those conditions. No command is automatically expanded from bare shorthand.

`agc.reset.interval` must be a multiple of four seconds. `advert.interval` allows 0 or even values from 60 to 240 minutes, deliberately excluding more aggressive intervals. `flood.advert.interval` allows 0 or 3–168 hours. Firmware may round other values; read-back must match exactly after numeric-format normalisation or the batch stops. Read-back equality confirms the returned configured value, not correct RF performance or successful reboot.

Single-node disruptive sets require `--allow-disruptive`: `repeat`, `tx`, `path.hash.mode`, `flood.max`, `flood.max.unscoped`, `flood.max.advert`, `loop.detect`.

Single-node actions require `--allow-disruptive`: `reboot`, `poweroff`, `shutdown`, `clkreboot`, `start ota`. Exactly one send attempt is made. Even a positive reply is not proof that a restart/OTA transition finished; result is `sent_unconfirmed`, exit 3. Inspect independently; do not resend due to the exit code. OTA mode entry does not upload firmware.

Blocked: password or identity changes, secret queries, raw command pass-through, erase/factory reset, room servers, ACL changes, firmware upload and radio/frequency migration. These need dedicated recovery and secret-safe server workflows. No client redaction can prevent a server from logging secrets deliberately sent as CLI text, so this version does not send such text.

## Validation and recovery

Offline: run `python -m unittest discover -s /PATH/TO/SKILL/tests -v`. Tests use fake contacts, simulated replies and local temporary files. They do not use your credentials or radios.

Live commissioning must be performed on your own environment:
1. Confirm the URL, certificate and complete target public keys independently; preferably populate the full-key allowlist.
2. Run `list`, and preview one explicitly selected `ver` query.
3. When authorised to query that node, apply the read. The script logs in and validates `get public.key` first. Do not assume `ver` is guest-accessible.
4. Choose one physically accessible, non-critical node for the first approved reversible setting change. Review the old setting, desired value and recovery access; verify it through this script and independently in RemoteTerm.
5. Expand to at most ten explicit targets only after that succeeds. Avoid simultaneous administrative requests from other clients or hosts.

Before any write the audit records target full key, observed firmware and the old setting. It is not a complete device backup. If there is no result after a write-intent record, execution is uncertain. Query the actual setting and compare it with the desired and old values. Restore only the reviewed old value if authorised and reachable; do not apply a whole batch of old values blindly. Physical/serial recovery may be needed after disruptive operations.

The lock is local, scoped to one state directory and canonical host name; it is not a distributed lease. Different DNS aliases or operator computers can bypass that scope. Adopt a single operator host and keep the URL/state directory stable. The upstream service may serialize individual requests, but that is not a batch ownership guarantee. Fixed delays do not prove a channel is free or enforce whole-network airtime limits.

## Sources and compatibility

Implementation reviewed against upstream source retrieved 5 November 2026. This is not certification against your installed versions. Live compatibility remains unverified until commissioning.

- MeshCore CLI reference: https://docs.meshcore.io/cli_commands/
- MeshCore CLI implementation: https://github.com/meshcore-dev/MeshCore/blob/main/src/helpers/CommonCLI.cpp
- Repeater admin permissions: https://github.com/meshcore-dev/MeshCore/blob/main/examples/simple_repeater/MyMesh.cpp
- RemoteTerm request/login implementation: https://github.com/jkingsman/Remote-Terminal-for-MeshCore/blob/main/app/routers/server_control.py
- RemoteTerm contact pagination: https://github.com/jkingsman/Remote-Terminal-for-MeshCore/blob/main/app/routers/contacts.py
- RemoteTerm security/deployment: https://github.com/jkingsman/Remote-Terminal-for-MeshCore/blob/main/README.md

Re-check API schemas and command semantics when updating RemoteTerm or firmware. Do not assume all MeshCore protocol messages lack correlation IDs: this script relies on RemoteTerm's CLI-response handling and cannot provide exactly-once delivery or cryptographic proof that a reply belongs to one command.

## Offline validation record

35 bundled regression tests passed on Linux/Python 3.12.14. An independent offline harness also passed nine end-to-end CLI scenarios with network sockets blocked and a simulated HTTP opener. It exercised target collisions on a later contacts page, verified two-node changes, timeout/read-back recovery, batch stopping, single-send reboot behaviour, minimum POST spacing and durable write-intent ordering. No real server, credentials or radio was used. Windows/macOS platform branches and your installed service/firmware versions require local commissioning.
