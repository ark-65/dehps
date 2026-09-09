# Immutable historical migration inputs

These two gzip JSON fixtures were read by exact `manifest_digest` from the
append-only `research_os_manifests` table, not from the current control-plane
head. They predate the active Formal P3 successor and contain the original
bounded-study and feasibility migration inputs. Their identities are checked
by `ControlPlaneManifest.from_dict` and again against their file names.
No fields, outcomes, identities or historical records were rewritten.

- `7fedbd48...`: `build_m4_v2_forward_evidence_feasibility_manifest.BASELINE_MANIFEST_DIGEST`
- `f4578685...`: `build_m4_v2_bounded_operational_forward_manifest.BASELINE_MANIFEST_DIGEST`

Compression uses gzip with mtime=0. Decode with Python `gzip.decompress` or
`gzip -dc`. Tests preserve the exact baseline manifest and resolver snapshot
checks, all dependency assertions, and the original unimplemented-successor
and Formal P4 wait requirements. The fixtures make those historical migration
tests independent of database availability and later production head changes.
