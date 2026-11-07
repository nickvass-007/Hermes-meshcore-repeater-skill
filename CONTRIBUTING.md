# Contributing

1. Open a sanitised issue describing the change and the affected API/firmware assumptions.
2. Keep safety policy changes explicit. Do not weaken targeting, TLS, secret handling, single-send writes, locking or outcome semantics as a shortcut.
3. Add offline regression tests before changing executable behaviour. No live-radio tests in CI.
4. Run `python3 -B tests/run_offline.py` and `git diff --check`.
5. Update documentation, version and changelog when behaviour changes. Regenerate `SHA256SUMS` after the final file set is settled; do not hash the manifest into itself.
6. Submit a pull request with actual test output and evidence limitations. Do not include secrets or private node data.

Preserve upstream attribution. Code/docs use MIT; MMTV artwork has separate terms and does not confer endorsement. Do not replace genuine artwork with a redrawn or recoloured mark.
