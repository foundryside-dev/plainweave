# Vendored SEI conformance oracle — provenance

`sei-conformance-oracle.json` in this directory is a **byte-verbatim** copy of
Loomweave's authoritative fixture:

    /home/john/loomweave/docs/federation/fixtures/sei-conformance-oracle.json
    (repo path: docs/federation/fixtures/sei-conformance-oracle.json)

Loomweave is the **producer / authority** for the six-scenario Weft SEI §8
conformance oracle (cargo gate `sei_conformance_oracle`). Plainweave is a
**consumer** and vendors the fixture so its conformance suite runs offline,
without a live Loomweave.

## Invariants

- **Never hand-edit** the vendored copy. Loomweave's oracle is the only author.
- The Layer-1 byte-pin (`UPSTREAM_BLOB_SHA` in
  `tests/conformance/test_sei_oracle.py`) reds the default suite on any byte
  change, so a tamper or an accidental edit is caught immediately.
- The Layer-2 drift recheck (`pytest -m sei_drift`) byte-compares this copy
  against the upstream sibling checkout (`LOOMWEAVE_REPO`, default
  `/home/john/loomweave`) — the release-gate drift alarm.

## Re-vendor procedure

1. Copy `$LOOMWEAVE_REPO/docs/federation/fixtures/sei-conformance-oracle.json`
   byte-verbatim over this file (`cmp` to confirm).
2. Recompute the git blob SHA and update `UPSTREAM_BLOB_SHA` in
   `tests/conformance/test_sei_oracle.py` **in the same commit**:

       python -c "import hashlib,sys; d=open(sys.argv[1],'rb').read(); \
         print(hashlib.sha1(b'blob %d\0'%len(d)+d).hexdigest())" \
         tests/conformance/fixtures/sei-conformance-oracle.json

3. Re-run conformance and conform the consumer
   (`src/plainweave/loomweave_adapter.py`) until green; never weaken the
   assertions.

Current vendored blob SHA: `0ea577025d94c028a0f682b7d29765079455718c`
(fixture_version 1, upstream `updated: 2026-06-02`).
