# Safety and security

## Use boundary

Operate only repeaters you own or are explicitly authorised to manage. Installation does not authorise live reads or changes. The `--apply` switch is not proof of human consent.

This is a privileged operator tool, not an internet-facing service. Keep RemoteTerm private/authenticated, verify TLS and confirm full public keys out of band. Do not broaden credentials, allowlists or command policy to bypass failed checks.

## Secrets and reports

- Keep `.env` outside the checkout; never commit it or paste it into chat/issues.
- Do not send admin passwords as radio CLI text. The supported login endpoint is distinct from CLI commands; RemoteTerm still receives login credentials and is a trusted dependency.
- Never attach raw journals, contact inventories, location settings, private URLs, CA keys or screenshots with secrets to public issues.
- For a suspected vulnerability, do not post exploit details or secrets publicly. Use GitHub private vulnerability reporting if enabled, or request a private reporting channel from the maintainer without including sensitive details. No private-reporting channel is assumed to exist.

## Failures and recovery

A missing reply is not success. Writes/actions are not retried by the client. Inspect the audit after interruption. A write intent without a result is uncertain; independently read actual state before deciding to restore a prior value. Restores require their own explicit approval. Shutdown or routing changes may remove remote recovery access.

A local lock is not distributed locking. Different aliases, operator hosts, UIs and other clients can interleave work. Use one canonical operator route and keep concurrent admin activity quiet.

No software safeguard establishes legal RF limits, correct antenna/hardware configuration or emergency-service availability. This package does not measure RF output or model propagation.
