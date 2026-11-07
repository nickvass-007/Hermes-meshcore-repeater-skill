# Usage and agent prompts

All prefixes in this page are illustrative, not target defaults. Use only your own explicitly authorised nodes. Run from the checkout root, or use the installed script's absolute path.

## HTTP-only preview

**Hermes:** “Load meshcore-repeater-command. Preview `get int.thresh` on `a1b2c3`. Do not apply.”

```sh
python3 scripts/repeater_cmd.py run --target a1b2c3 --command "get int.thresh"
```

Expected: a plan with a resolved full key; no repeater login or radio CLI. HTTP health/contacts are still contacted.

## Read firmware

**Hermes:** “Show firmware on `a1b2c3`. Radio queries are authorised; do not change configuration.”

```sh
python3 scripts/repeater_cmd.py run --target a1b2c3 --command "ver" --apply
```

Expected: login, identity check, query, `read_ok`, and a private audit. A firmware query is read-only but consumes radio airtime.

## Preview and verify a setting change

**Hermes:** “Preview setting `int.thresh` to `0` on `a1b2c3`. Do not apply yet.”

```sh
python3 scripts/repeater_cmd.py run --target a1b2c3 --command "set int.thresh 0"
```

After reviewing the full key and authorising that exact change:

```sh
# Replace the placeholder with the full key returned by the preview.
python3 scripts/repeater_cmd.py run --target YOUR_64_HEX_PUBLIC_KEY --command "set int.thresh 0" --apply
```

**Hermes:** “Set `int.thresh` to `0` on this full key: `<YOUR_64_HEX_PUBLIC_KEY>`. Record the old value and verify the returned configuration.”

Expected: `unchanged` if already matching, otherwise `verified_config` only when read-back matches. Firmware support must be established first. This example is not a tuning recommendation.

## Multiple explicit targets

**Hermes:** “Preview `get int.thresh` on `a1b2c3` and `d4e5f6`; no other nodes.”

```sh
python3 scripts/repeater_cmd.py run --target a1b2c3 --target d4e5f6 --command "get int.thresh"
```

Use both resolved full keys on a subsequent approved apply. Maximum ten ordinary targets. A failure stops the batch; do not resume automatically.

## Disruptive operations

Do not use a reboot as the first commissioning test. A reboot temporarily interrupts service; shutdown may require physical recovery. Disruptive sets include routing/repetition and transmit-power controls. These require one explicitly selected node, informed approval and `--allow-disruptive`.

**Hermes:** “Reboot `a1b2c3` once. I accept the temporary outage. Do not resend it if the reply is missing; report the result as unconfirmed until independently checked.”

```sh
python3 scripts/repeater_cmd.py run --target a1b2c3 --command "reboot" --apply --allow-disruptive
```

Expected: one send attempt; `sent_unconfirmed` and exit 3 even after a positive acknowledgement. Do not interpret this exit code as permission to retry. OTA mode entry does not upload firmware.

## Alternate configuration location

Global options come before the subcommand:

```sh
python3 scripts/repeater_cmd.py --env-file /secure/local/meshcore.env run --target a1b2c3 --command "ver"
```

Only give the agent the file path, never its contents. Keep a common state directory/canonical URL; do not alter paths to evade locks.

## Results

| Status | Meaning / next step |
|---|---|
| `read_ok` | Supported query returned a non-error reply. |
| `unchanged` | No setting write was needed. |
| `verified_config` | Returned configuration matches; behaviour/RF remains separately tested. |
| `rejected` | Explicit rejection; stop. |
| `verification_mismatch` | Returned value differs; investigate, do not blindly resend. |
| `unconfirmed` | Write may have executed; read actual state before deciding. |
| `sent_unconfirmed` | Action send attempted, transition not proven. |
| `failed` | Precondition/login/read failed; inspect private audit. |
| `skipped_after_failure` | No command attempted for that remaining target. |

Exit codes: 0 for preview/read/verified/unchanged; 2 aborted; 3 incomplete/rejected/mismatch/unconfirmed; 130 interrupted. Nonzero means inspect, not retry.

## Recovery prompt

“Inspect the private audit for the failed run without exposing secrets. Report the exact target, intended change, previous value and uncertainty. Do not retry or revert. Ask for authority before any live read or recovery operation not already authorised.”

Examples are documentation, not evidence of live radio testing.
