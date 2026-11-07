<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/mmtv-lockup-on-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="assets/mmtv-lockup-on-light.png">
  <img alt="MMTV" src="assets/mmtv-lockup-on-light.png" width="316">
</picture>

# Hermes MeshCore repeater skill

**MMTV Mesh · Explicit targets. Preview first. Verify configuration.**

A Hermes skill and standard-library Python CLI for managing **your own explicitly selected MeshCore repeaters** through an existing [RemoteTerm](https://github.com/jkingsman/Remote-Terminal-for-MeshCore) server.

It helps an agent query firmware, inspect supported settings and make bounded configuration changes without guessing node names or silently targeting a fleet.

> **Status:** v2.0.0 execution bundle, offline regression tested. Live RemoteTerm/firmware commissioning is still required in each environment. This is not a radio dashboard, firmware installer or proof of RF performance. No live radio acceptance is claimed.

[Setup](references/setup.md) · [How it works](docs/how-it-works.md) · [Usage and prompts](docs/usage.md) · [Safety](SECURITY.md) · [Compatibility](docs/compatibility.md) · [Changes](CHANGELOG.md)

## What it does

| Capability | Behaviour |
|---|---|
| Explicit targeting | Exactly six hexadecimal public-key characters, or a full 64-character key. Never names, wildcards, implicit favourites or all nodes. |
| Complete lookup | Fetches every contact page; collisions with non-repeaters count too. Invalid, duplicate or non-repeater targets abort the operation. |
| Preview by default | Reads HTTP health and contacts only. No repeater login or radio CLI command until `--apply`. |
| Verified identity | On apply, logs in and checks the remote full public key before the requested command. |
| Bounded changes | Captures firmware and old value, journals intent, sends the setting once, then reads back and compares. |
| Conservative traffic | Sequential POSTs, minimum four seconds after each POST finishes, maximum ten ordinary targets. |
| Honest outcomes | Rejects errors, stops on mismatch/uncertainty, and never treats silence as success. |
| Local audit | Private JSONL records and a local hostname-scoped execution lock. |

Supported settings and local bounds are listed in [setup](references/setup.md). Raw CLI, passwords/private-key commands, factory reset, ACL edits, radio/frequency migration and firmware flashing are blocked. Disruptive actions are single-node only and require explicit approval plus `--allow-disruptive`.

## Requirements

- Python **3.10+**; no pip packages.
- Hermes for natural-language agent use; the CLI also works without Hermes.
- An existing, trusted RemoteTerm service reachable from the operator machine over **verified HTTPS**, or an authenticated/encrypted local tunnel with the narrowly permitted loopback HTTP option.
- Repeater admin credentials for live node queries or changes; HTTP Basic credentials only if your web server uses them.
- Confirmed full public keys for the repeaters you manage. A full-key allowlist is recommended.

This package talks to RemoteTerm's HTTP API. It does **not** open a second direct TCP/serial radio connection, deploy RemoteTerm, create TLS certificates or change your server authentication.

## Install and test offline

```sh
git clone https://github.com/nickvass-007/Hermes-meshcore-repeater-skill.git
cd Hermes-meshcore-repeater-skill
python3 -B tests/run_offline.py
python3 -B scripts/repeater_cmd.py --version
```

Review the source and `SHA256SUMS` before use. On Linux, `sha256sum -c SHA256SUMS` checks the published file bytes; it does not establish who signed or authored them.

To install the skill into the **default** Hermes profile on Linux/macOS, run from the checkout:

```sh
mkdir -p "$HOME/.hermes/skills"
# This refuses an existing destination. Stop and back up an existing copy first.
mkdir "$HOME/.hermes/skills/meshcore-repeater-command" && cp -R SKILL.md scripts references tests .gitignore   "$HOME/.hermes/skills/meshcore-repeater-command/"
```

For a named profile or custom Hermes home, use that profile's actual `skills` directory instead. Do not install into another profile implicitly. In Hermes, load `/skill meshcore-repeater-command`; use `/reload-skills` or start a fresh session if required by your client.

## Complete local configuration

Do not paste secrets into agent chat. Use a trusted local terminal/editor. These commands refuse to replace an existing `.env`:

```sh
mkdir -p "$HOME/.hermes/secrets/meshcore"
chmod 700 "$HOME/.hermes/secrets/meshcore"
(umask 077; set -C; cat references/meshcore.env.example > "$HOME/.hermes/secrets/meshcore/.env")
chmod 600 "$HOME/.hermes/secrets/meshcore/.env"
```

Edit the file locally. Replace example values; do not use the dummy credentials.

| Key | What to enter |
|---|---|
| `RT_BASE` | RemoteTerm HTTPS origin, including a port if needed; no `/api` path. |
| `MESHCORE_REPEATER_PASSWORD` | Repeater admin password; use per-node entries where passwords differ. |
| `RT_USER`, `RT_PASS` | Optional HTTP Basic credentials; configure both or omit both. |
| `RT_CA_FILE` | Optional verified private CA/certificate file. Do not disable TLS verification. |
| `MESHCORE_ALLOWED_KEYS` | Recommended comma-separated trusted full public keys. |

The file is read literally, without shell execution or variable expansion. On POSIX it must be an owned regular file with mode `0600` or `0400`; use restrictive account ACLs on Windows. See [setup](references/setup.md) for per-node credentials and tunnel constraints.

## First use

Examples below use the **illustrative** prefix `a1b2c3`. Replace it with your own verified target. Do not run it as a default node.

```sh
# HTTP contact inventory only; no repeater login or radio CLI.
python3 scripts/repeater_cmd.py list

# HTTP-only preview of a firmware query.
python3 scripts/repeater_cmd.py run --target a1b2c3 --command "ver"

# Only after explicit permission: this logs in, validates identity and queries over radio.
python3 scripts/repeater_cmd.py run --target a1b2c3 --command "ver" --apply
```

For separate preview/apply calls, use the **full public key printed by the preview** in the apply call. Confirm a single-node read before approving any configuration change.

In Hermes, say:

> Load `meshcore-repeater-command`. Preview a firmware query on `a1b2c3`. Do not apply or send radio commands.

Then, after reviewing the target:

> Query the firmware on this confirmed full public key: `<YOUR_64_HEX_PUBLIC_KEY>`. Do not change settings.

More [prompt and CLI examples](docs/usage.md) cover supported reads, verified writes and failure recovery.

## How it fits together

```text
Operator request -> Hermes skill / CLI -> policy and target validation
                                           |
                                RemoteTerm health + all contacts
                                           |
                             preview: print plan and stop
                                           |
                             apply: login + verify full key
                                           |
                      read OR pre-read -> journal -> one write -> read-back
                                           |
                          private audit + explicit result status
```

**Preview is not offline.** A read-only apply still sends radio traffic. Matching a returned setting confirms configuration, not RF output, runtime behaviour or a reboot. A local lock is not a distributed lease; keep other administrative clients quiet during a batch.

## Maintenance and recovery

- Run `python3 -B tests/run_offline.py` after code changes.
- Review upstream API and firmware semantics before updates; do not auto-update and assume compatibility.
- Inspect the private audit under `~/.hermes/state/meshcore/` after an interrupted or uncertain operation.
- Read the actual setting before deciding what to do next. Never blindly repeat a write, reboot, shutdown or OTA action.
- Restoring a saved old value is a **separate authorised operation**, not automatic rollback.
- Installing or removing the skill does not undo radio changes. Back up an existing skill before replacing it; never delete credentials as part of uninstall.

## Licence, branding and upstream projects

Code and documentation are [MIT licensed](LICENSE), **excluding artwork in `assets/`**, which has separate [brand terms](assets/BRAND-TERMS.md). MMTV Mesh presentation uses the genuine supplied artwork; it does not grant endorsement or trademark rights.

This is an independent MMTV project, not an official MeshCore, RemoteTerm or Nous Research release. MeshCore and RemoteTerm are separate dependencies, not bundled code. See [attribution](NOTICE.md).
