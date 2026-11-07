# Compatibility and commissioning

## Tested scope

The original supplied v2.0.0 package records 35 offline regression tests on Linux/Python 3.12.14 and nine separate simulated CLI scenarios. Those are historical supplier claims, not additional tests executed by this repository's publisher.

For public packaging, the bundled 35-test suite is rerun with network connection/DNS guards. The GitHub workflow exercises Python 3.10, 3.12 and 3.14 on Linux. Inspect the actual workflow result for the exact commit; a workflow definition alone is not a passed run.

The implementation requires Python 3.10+. Windows/macOS branches exist but are not claimed as platform-validated by this Linux publication. No live server/firmware pair is certified by these offline tests.

## API assumptions

The client expects:

- `GET /api/health` with `radio_connected: true` for a run.
- `GET /api/contacts?limit=1000&offset=...` returning list pages with full public keys and repeater `type: 2`.
- `POST /api/contacts/{full_key}/repeater/login` returning `authenticated: true`.
- `POST /api/contacts/{full_key}/command` returning a string `response`.
- Supported firmware `get` replies beginning with `> `.

Pagination is bounded at 100,000 contacts; duplicates, malformed entries and an exhausted page bound abort. Schema or formatting differences are not a reason to remove safety checks.

## Commission your own environment

1. Independently confirm the RemoteTerm URL, certificate trust, complete node keys and ownership.
2. Configure credentials locally. Prefer a full-key allowlist.
3. Run `list`, then preview one explicitly selected `ver` query.
4. Authorise and execute that read. Check remote full identity and actual firmware reply.
5. Choose one physically accessible, non-critical node for an approved reversible setting test. Record recovery access and old value; verify through this CLI and independently in RemoteTerm.
6. Expand only after successful acceptance. Keep other administrative clients quiet.

Do not expose an unauthenticated RemoteTerm service publicly to make this package work. HTTPS verification cannot be disabled. Plain HTTP is limited to an explicitly enabled literal loopback address behind an independently secured tunnel, never a LAN/tailnet HTTP exception.

Review upstream schemas/command semantics whenever RemoteTerm or firmware changes. See [source links](../NOTICE.md).
