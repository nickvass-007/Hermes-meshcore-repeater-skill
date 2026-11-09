# Phase-specific repeater troubleshooting

## Scope and prerequisites

Use this reference when a guarded operation fails, outcomes vary between runs, or a short selector is ambiguous. Read the private-recording procedure first. Keep the bundled `scripts/repeater_cmd.py` as the sole radio-command execution path; do not use diagnostics to bypass a denied command, identity mismatch, allowlist, TLS policy or original OS lock.

The labels below classify operator evidence. They are not new CLI options or a promise that the native `failed` result already names the phase. Do not infer the phase from a generic timeout alone.

## Select an identity before testing

1. Validate the supplied selector literally before lookup. An invalid-length token needs an exact correction or exclusion; never truncate it.
2. Resolve against all paginated contacts, not only favourites or recently seen nodes. Validate each candidate full key as exactly 64 hexadecimal characters.
3. When multiple contacts share a prefix, show names and exact full keys and obtain the operator's selection. A favourite flag, familiar name or newer cache timestamp is not identity proof. Never silently discard an old contact to make the prefix unique.
4. Pin the selected full key in the preview and apply. Preserve the original blocked result; a subsequent full-key operation is a fresh request, not a retroactively successful prefix query. Historical operator-confirmed keys are useful context, not an implicit native prefix alias or permission to change an allowlist.

## Classify the observed phase

| Evidence | Classification | Safe next step |
|---|---|---|
| Missing/ambiguous/disallowed target or invalid selector | Preflight blocked | Resolve exact identity or missing authority; no radio attempt. |
| Login API does not confirm authentication | Login unconfirmed | Inspect selected-node server evidence, reachability and local credential configuration without exposing secrets. A timeout does not prove an incorrect password. |
| Authentication confirmed, but full public-key read gets no reply | Identity-read failure | Stop before the requested command. Correlate route snapshots and server logs; do not bypass identity or retry login as a substitute. |
| Full identity matches, then the requested read exhausts its attempts | Requested-read failure | Inspect that command's response/timeout evidence and permissions/compatibility; do not relabel it as a login failure. |
| HTTP/API returns successfully but contains a no-response placeholder | No confirmed radio reply | HTTP success alone is not command success. Preserve the placeholder and phase. |
| Parser rejects a reply that actually arrived | Reply-format failure | Inspect exact sanitised bytes and deployed response extraction, then reproduce with synthetic tests before changing parsing. Do not loosen full-key matching. |

Never turn missing responses into a specific credential, RF or firmware diagnosis without supporting evidence. A past successful identity read on the same full key argues against assuming that the command is universally unsupported, but does not establish current reachability.

## Distinguish routing modes

A normal invocation means no additional operator routing override was requested. It does not mean no flood traffic: RemoteTerm can use a stored flood route or perform its native flood-login fallback. Check bounded selected-node server logs and record any fallback separately from client retry counts.

In some deployed versions, login fallback resets the radio path, while the next CLI handler reloads the contact using its saved effective route. Check the deployed implementation before claiming a successful flood login guarantees flood identity/CLI reads. A cached route of any hop length can be stale. Contact cache metadata is not a verified physical RF path and may change during a request.

Check both the effective path tuple and its source label when deciding whether a contact is already using flood. A forced-flood override can have an effective flood path while its source is labelled `override`; a fallback check that recognises only a `flood` source label can perform another flood-login attempt unnecessarily. Verify the deployed branch and selected-node logs before attributing an extra attempt, and distinguish one client API request from the server's internal attempts. Do not silently patch a production server or claim this explains failures in later phases.

If an ordinary read succeeds only after native fallback or its second permitted attempt, report those qualifications. Do not claim the starting route worked throughout or that reliability is established.

## Separately approved temporary routing experiment

The bundled CLI has no forced-flood option. Do not invent `--flood`, silently patch the server, or treat read permission as routing-write authority. A version-checked native control-plane experiment needs explicit exact-target approval and a separately reviewed integration around the unchanged guarded workflow.

Before any approved experiment, capture the exact previous override, verify canonical logging and preserve the original lock across activation, guarded reads and finally restoration. Verify the intended effective route before each radio POST. Record mutation intent before sending it; an uncertain activation response still requires reconciliation and the authorised cleanup. Restore and read back the previous override before another node starts. Preserve naturally learned routes instead of overwriting the whole contact with an old cache snapshot.

Test cleanup offline for success, command failure, uncertain activation response and logging failure. If recording fails after activation, stop new tests but still attempt the authorised restoration and retain local recovery evidence. Stop all further radio work if restoration is uncertain. Ordinary setting rollback rules remain unchanged: this temporary cleanup must be explicitly included in the experiment's approval.

One contact's experiment does not authorise fleet overrides. A fleet experiment needs fresh fixed-list authority, serial per-node guarded invocations, unchanged exclusions/collision blocks, per-node restoration, visible progress and a final independent override readback. Never replay consumed or interrupted requests automatically.

## Learn from comparisons without overclaiming

- Preserve earlier per-selector ledgers and complete sanitised outputs. Compare newly successful nodes, lost successes, unchanged outcomes, blocked selections and exclusions, not just totals.
- Measure requested timing gaps from POST completion and across node invocations. More delay is a hypothesis, not a guaranteed fix or new permanent default.
- Separate successful coverage from successful replies. A controller exit of zero can mean the finite list finished with failures.
- A workaround that helps one node but does not improve the complete fleet result is not evidence for a permanent fleet-wide policy. RF variation, concurrent users, route learning and server/session state can confound before/after results.
- Record what was proven, what failed, what remains a hypothesis and the next evidence needed. Use foreground batches or a verified completion handoff with visible progress; launching a background process is not completion ownership.
- Keep real node identifiers, local configs, credentials, audits, private wrappers and raw logs out of public repositories and CI. Publish only generic guidance and synthetic regressions; preserve runtime version and publication commit separately.
