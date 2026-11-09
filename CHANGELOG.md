# Changelog

## Unreleased — operator guidance only

- Reconcile installed and public request-recording, coverage, paced-comparison and closeout guidance.
- Add phase-specific troubleshooting: distinguish login, full-key identity, requested-read and reply-format failures; preserve collision decisions and exact full keys.
- Document native flood-login fallback versus sustained routing, separately approved temporary-override lifetime and restoration, and the limits of before/after fleet comparisons.
- Distinguish an effective flood path from a routing-source label when diagnosing redundant native login fallback; verify server-internal attempts rather than counting only API calls.
- Retain runtime v2.0.1 without execution, retry, parsing, TLS, allowlist or CLI-option changes. No private node data, deployment configuration or diagnostic wrappers are published.

## 2.0.1 — strict public-key reply compatibility

- Accept bare or `> `-prefixed 64-character hexadecimal public-key replies, including uppercase keys and one LF/CRLF transport terminator.
- Retain exact full-key target matching; reject partial, malformed, multiline, whitespace-padded and mismatched identities before the requested command.
- Use the same strict identity parser for an explicit `get public.key` read. Generic setting parsing, command policy, write retries, TLS and target selection are unchanged.
- Add synthetic-key regression coverage for successful reads and rejection paths. No deployment credentials or real node identifiers are included.
- Document private agent-managed request/output logging, exact selector preservation, explicit exclusions and approved independent serial read campaigns. Bare CLI auditing remains separate; no hidden Obsidian-writing hook or radio schedule is installed.
- Exclude installed-only local operations references and operation-log folders from Git.

## 2.0.0 — public MMTV Mesh packaging

- Preserve the supplied v2.0.0 execution bundle byte-for-byte.
- Add public setup instructions, architecture and trust boundaries, practical CLI/agent examples, security guidance and contributor notes.
- Add an offline test runner with network connection/DNS guards and a Linux Python CI matrix.
- Add genuine MMTV light/dark artwork and separate brand-use terms.
- Add MIT code/documentation licensing and source attribution.

No RemoteTerm connection, radio query or configuration change forms part of packaging. Offline regression coverage is not live firmware/API certification. The original package's historical validation record is retained in its reference document and distinguished from publisher-run checks.
