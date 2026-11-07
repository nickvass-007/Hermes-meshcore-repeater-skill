# How it works

## Execution path

1. The CLI classifies the command against a fixed policy before constructing a network client. There is no arbitrary command pass-through.
2. It loads the selected local `.env` literally. It does not source it, interpolate variables, inherit config overrides or print credentials deliberately.
3. For `run`, it takes a private local lock keyed by the canonical hostname, checks radio-connected health and retrieves all contact pages.
4. It resolves every selector before login. A prefix must be unique across all contact types. Targets must be repeaters and, when configured, present in the trusted full-key allowlist. Duplicate selectors abort.
5. Without `--apply`, it returns the command, risk and full-key plan. No radio login or CLI request is sent.
6. Apply requires passwords for every target. Per node, it rechecks health, logs in once and queries `get public.key` to match the full identity.
7. Reads have at most two attempts for missing replies or uncertain transport errors. Explicit HTTP/error responses are not blindly retried.
8. Sets read firmware and the old value. Already-matching values return `unchanged` without a write. Otherwise the audit is fsynced with the write intent before sending once.
9. A set is read back. Numeric formatting is normalised exactly, without loose tolerance. A mismatch or unknown final value stops the batch. Remaining nodes are marked skipped.
10. Actions get one send attempt and remain `sent_unconfirmed` even with a positive reply. Independent evidence is required to establish the actual transition.

## Trust and concurrency limits

- Six characters select a contact; they do not prove ownership. Use independently confirmed full keys and an allowlist.
- RemoteTerm, its contact inventory and firmware remain trusted dependencies. Checking the reported key is not a cryptographic command-to-response proof.
- The script cannot guarantee exactly-once delivery through a remote server or radio mesh. It guarantees no client-side retry of configuration/action sends.
- RemoteTerm may perform its own login routing/flood retry.
- Four-second POST spacing and serial client requests reduce load; they do not measure channel occupancy or enforce mesh-wide fairness.
- The lock covers this script on one host with a common state directory and canonical hostname. Aliases, other machines, the UI and other clients can bypass that scope.
- `list` retrieves contact inventory without a radio command; it is not a radio health test and does not take the run lock.

## Private local state

The default credential file is `~/.hermes/secrets/meshcore/.env`. Audit and lock files go to `~/.hermes/state/meshcore/`. Keep both outside the repository. Audits may contain names, public keys, configuration and location settings; do not publish raw journals. Redaction is defence in depth, not permission to publish logs.

A write intent without a result is uncertain. Read actual state before any recovery. Review old values, recovery access and other operator activity; do not automatically replay or revert a batch.
