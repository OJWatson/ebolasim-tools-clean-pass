# CI / Release Completion Plan (Unfinished Work)

This plan tracks the remaining work to fully operationalize the new pinned-upstream build-and-release flow.

## Current status

Implemented:

1. Pinned upstream lock schema and fetch helpers.
2. Bundled executable staging/resolution helpers.
3. CI and release workflows that build from pinned upstream and verify reproducibility.
4. Tests and documentation for upstream fetch and bundled executable behavior.

Not yet completed:

1. Real upstream lock values are still placeholders and must be replaced.
2. Release publication has not been validated end-to-end on GitHub with a real tag.
3. Governance/process for lock updates and provenance review is not yet documented as an operational runbook.

## Completion criteria

The work is complete when all items below are true:

1. `legacy-src/upstream.lock.yml` and `src/ebolasim_tools/legacy_patches/upstream.lock.yml` contain real upstream values.
2. CI `build_pinned` job passes on `main`.
3. A tagged release run succeeds and uploads:
   - wheel (`.whl`);
   - source distribution (`.tar.gz`);
   - release bundle archive with checksums and metadata.
4. Installed wheel on Linux resolves bundled executable successfully.
5. Team has a documented lock-update and review procedure.

## Phase 1: Finalize upstream pin

1. Identify the authoritative public upstream repository and exact commit/tag to pin.
2. Download the source archive for that exact ref and compute SHA256.
3. Update both lock files:
   - `legacy-src/upstream.lock.yml`
   - `src/ebolasim_tools/legacy_patches/upstream.lock.yml`
4. Ensure `strip_prefix` matches archive extraction root.
5. Open PR with provenance evidence (archive URL, SHA256 command output, selected ref rationale).

## Phase 2: CI hard validation pass

1. Trigger CI on updated lock PR.
2. Confirm jobs pass:
   - lint/tests;
   - double-build reproducibility hash check;
   - wheel install + bundled executable probe.
3. Review uploaded CI artifacts:
   - `release-bundle-a`;
   - `release-bundle-b`;
   - `python-dist`.
4. Record resulting binary SHA256 for release notes/provenance.

## Phase 3: Release dry-run then real release

1. Create a release-candidate tag (or test tag path) and run `release.yml`.
2. Verify expected assets are attached to the GitHub release.
3. Validate metadata contents in release bundle:
   - `upstream_fetch.json`;
   - `build_metadata.json`;
   - `run_metadata.json`;
   - `checksums.txt`.
4. Run one post-install smoke check from released wheel on Linux.
5. Publish final release tag once dry-run outcomes are accepted.

## Phase 4: Operational runbook and ownership

1. Add maintainer runbook section covering:
   - how to update upstream lock safely;
   - required verification commands;
   - approval checklist for lock changes.
2. Require explicit reviewer approval for lock changes (code owners or PR template checklist).
3. Add periodic lock-review cadence (e.g. quarterly) with explicit “no change” option.

## Risks and mitigations

1. Upstream archive URL drift:
   - Mitigation: lock by immutable commit archive and checksum; fail fast in CI on mismatch.
2. Non-deterministic compile output:
   - Mitigation: in-job double-build hash comparison and pinned compiler environment.
3. Shipping wrong binary in wheel:
   - Mitigation: post-build wheel install + `resolve_bundled_executable()` assertion.
4. Lock file divergence between source and package-data copy:
   - Mitigation: keep both files updated in the same PR and include checklist item in review template.

## Suggested command checklist for maintainers

```bash
# 1) Update lock files with real values
$EDITOR legacy-src/upstream.lock.yml
$EDITOR src/ebolasim_tools/legacy_patches/upstream.lock.yml

# 2) Local validation
python -m ruff check src tests tools/ci
python -m pytest -q

# 3) Commit and push
git add legacy-src/upstream.lock.yml src/ebolasim_tools/legacy_patches/upstream.lock.yml
git commit -m "Pin upstream lock to real public ref and checksum"
git push
```
