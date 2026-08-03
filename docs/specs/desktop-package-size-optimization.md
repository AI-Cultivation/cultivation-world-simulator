# Desktop Package Size Optimization

## Status

Planned. This specification covers the GitHub standalone package, the Electron
desktop package, and the shared content consumed by Steam and Epic. It does not
change gameplay assets merely because they are large: every removal or
conversion must have a runtime-usage and visual-quality decision behind it.

## Context

The `v4.0.2` generic desktop `win-unpacked` package is 692.76 MiB. The largest
contributors are:

| Area | Size | Notes |
| --- | ---: | --- |
| Bundled game assets | 294.73 MiB | `avatars` 104.25 MiB, `yao` 109.72 MiB, screenshots, splash media, sects, tiles, and bundled saves. |
| Electron / Chromium runtime | about 284 MiB | Main executable is 191.91 MiB; Chromium locale packs are 41.58 MiB. |
| Frontend BGM | 52.26 MiB | Five MP3 files account for almost all of this total. |
| Backend runtime and configuration | about 61.75 MiB | Python runtime, native modules, backend EXE, and static data. |

The package also contains two byte-for-byte identical copies of `static/`:
`resources/backend/static` and `resources/backend/_internal/static`. Each is
6.25 MiB with 791 files. The current scripts both pass `--add-data static;static`
to PyInstaller and copy `static/` next to the backend executable after the
PyInstaller build.

The `tmp/v4.0.2_desktop` build workspace is larger, at 1,101.46 MiB (shown by
Windows Explorer as 1.07 GB). This is expected during a build: it contains the
408.70 MiB PyInstaller intermediate `backend_dist` as well as the same 408.70
MiB backend copied into the final `win-unpacked/resources/backend`. Only
`win-unpacked` is the desktop content root for testing or store distribution;
`backend_dist` is not part of the delivered package.

## Goals

1. Reduce installed desktop size without lowering the visual quality or
   availability of shipped gameplay content.
2. Make resource inclusion explicit, auditable, and shared by GitHub, Desktop,
   Steam, and Epic packaging.
3. Keep editable source media separate from release-eligible optimized media.
4. Remove release-ineligible files and duplicate runtime data only after proving
   they are not needed by packaged execution.
5. Add repeatable package-size reports and size-budget regression checks.

## Non-Goals

1. Do not build a separate game-content download service in this iteration.
2. Do not make runtime asset availability depend on a network connection.
3. Do not optimize source code bundles before addressing media and runtime
   packaging, which account for nearly all current size.
4. Do not trade a smaller installer for a larger installed application without
   recording both measurements separately.

## Distribution Decision

There are two distinct kinds of compression and they must not be conflated.

### Release-resource optimization

Image, video, and audio optimization belongs at the shared resource layer,
before either GitHub or Desktop packaging. One tested release-resource manifest
will define exactly which optimized assets each package consumes.

This avoids a GitHub build using one set of assets while the Electron, Steam,
or Epic build uses another. It also avoids per-package lossy re-encoding, which
would make release output hard to reproduce and hard to visually review.

Editable high-quality originals, where they must be retained, remain outside
the release manifest. They may live in a clearly named source-media location or
be managed with Git LFS; they must never be copied by a broad `assets/` rule
into a release package.

### Channel delivery compression

Archive compression is a final delivery concern, after the resource set has
already been optimized.

| Channel | Delivery rule |
| --- | --- |
| GitHub | Continue producing a ZIP from the clean PyInstaller directory. ZIP reduces download size but does not remove unused assets or improve the extracted size. |
| Desktop local test | Keep `win-unpacked` as the inspectable test artifact. Its size is the installed-size baseline. |
| Steam / Epic | Consume the same clean desktop content root. Store upload tooling handles transport, patching, and compression; it must not produce a different asset set. |
| Future installer | If an NSIS/MSI installer is added, report installer download size separately from installed size. |

Therefore, the answer is neither "compress only GitHub" nor "compress only
while packaging Desktop": optimize common release resources once, then let each
channel apply its normal transport/archive compression.

The initial implementation performs lossless PNG optimization in the shared
staging step with Pillow. It preserves original files and paths, and reports
the resulting byte savings. PNG results are cached by source content hash so
subsequent GitHub and Desktop builds do not repeat the expensive compression.
Human and yao avatar release copies are additionally downscaled from 512px to
384px using nearest-neighbor resampling; source assets remain unchanged.
MP3 re-encoding remains gated on a checked-in
FFmpeg-based tool and an A/B listening approval; it must not be substituted by
generic archive compression.

## Proposed Architecture

### Release manifest and staging

Introduce a versioned release-resource manifest and a build tool that produces
a clean, reproducible staging directory. The manifest must list included asset
groups, excluded source-only files, and required output paths. It must not use
an unrestricted `assets/` copy as the package contract.

The GitHub PyInstaller script and `tools/package/desktop/pack.ps1` consume the
same staging directory. Steam and Epic remain consumers of the Desktop content
root and do not gain their own media transformation path.

The staging tool must:

1. Start from a clean generated directory under `tmp/`, never mutate checked-in
   release assets during normal packaging.
2. Validate every manifest entry and fail on an unknown, missing, or oversized
   file without an explicit allow-list justification.
3. Emit JSON and Markdown reports with totals by top-level group, largest files,
   duplicate-content findings, and comparison with the prior baseline.
4. Preserve application-relative paths so Python and frontend runtime URLs do
   not change as an incidental result of the optimization.
5. Report build-workspace size separately from final-content-root size. It must
   identify transient duplicate inputs such as `backend_dist` rather than
   presenting them as shipped package bloat.

### Packaging input rules

1. Replace broad copies of the whole asset tree with the release staging tree.
2. Keep `web/public` and frontend build output distinct from Python asset input;
   BGM remains in the frontend public-resource group.
3. Explicitly document any intentional packaged demo save. Otherwise remove
   `assets/saves` from release staging and retain it only as development or test
   material.
4. Retain `splash.png` and `splash.mp4` only after checking the production
   splash flow, because they are runtime-referenced by `SplashLayer.vue`.
5. Exclude README-only media such as `assets/screenshot.gif` from release
   staging unless a packaged runtime reference is discovered.

## Work Plan

### Phase 0: Baseline and safety net

1. Add a package inventory tool that records unpacked total size, grouped
   directory sizes, largest files, duplicate files by SHA-256, Electron locale
   files, and PyInstaller modules.
2. Generate baselines for GitHub and generic Desktop packages. Record both
   unpacked/installed size and compressed delivery size where applicable.
3. Add package contract tests that assert a clean release contains no logs,
   user saves, source media, source maps, credentials, or undeclared top-level
   resource groups.
4. Add a manual test checklist for splash media, avatar rendering across races
   and realms, BGM switching, map tiles, sect images, save/load, and all enabled
   UI locales.

### Phase 1: Remove proven non-runtime content

1. Trace each large file and directory from source reference to packaged runtime
   reference. Record one of: required, optional, development-only, documentation-
   only, or obsolete.
2. Exclude documentation-only `screenshot.gif` and `screenshot.png` from
   release staging after search and packaged smoke tests confirm no runtime use.
3. Decide whether bundled saves are a supported product feature. If not, remove
   them from release staging and add a contract test that user data begins in
   `CWS_DATA_DIR`, not inside the application assets.
4. Remove only one of the duplicated `static/` copies. First test packaged
   path resolution in a frozen build; retain the location that the runtime
   deliberately resolves and remove the other PyInstaller/copy operation.
5. Rebuild GitHub and Desktop packages and compare the reports before advancing.

### Phase 2: Optimize shared media

1. Create an asset inventory for `avatars`, `yao`, `sects`, `tiles`, cities,
   splash media, and BGM, including dimensions, alpha usage, format, bitrate,
   and actual UI display size.
2. Establish per-class visual acceptance rules before converting anything:
   pixel-art edges, transparency, race-identifying details, and realm-specific
   visual differences must remain legible at shipped UI sizes.
3. Trial representative image conversions and dimension reductions in a staging
   branch. Compare rendered screenshots at the actual frontend scale; do not
   approve based only on file-browser thumbnails.
4. Apply approved conversions uniformly through the shared release-resource
   tool. Keep originals outside the release manifest when continued editing
   requires them.
5. Audit the five large BGM tracks. Re-encode only after an A/B listening test
   and document bitrate/sample-rate choices. Do not change the public runtime
   filenames without updating the frontend playlist contract.

### Phase 3: Shrink runtimes without changing gameplay assets

1. Configure Electron Builder to ship only the Chromium locales corresponding
   to enabled product UI languages. Verify locale codes against Electron's
   actual `.pak` names and test application startup under every enabled UI
   locale.
2. Audit PyInstaller's analysis output and runtime contents in a clean runtime-
   dependencies environment. Investigate development-oriented imports such as
   `jedi`, `mypy`, `IPython`, `astroid`, `watchfiles`, and `pythonnet`.
3. Remove dependencies only when import tracing and a packaged smoke run prove
   they are not required. Prefer fixing accidental imports or build-environment
   contamination over blindly extending the PyInstaller exclude list.
4. Preserve required native dependencies such as Python, Pydantic Core, SQLite,
   OpenSSL, and frontend browser support DLLs unless a tested replacement exists.

### Phase 4: Enforce the release contract

1. Make GitHub and Desktop packaging fail if they consume a non-clean staging
   tree or produce different shared resource manifests.
2. Have the Desktop pack script verify `app.asar`, `resources/backend`, and
   Electron locale contents after packaging, as already done for source maps
   and sensitive configuration.
3. Publish the size report beside local build markers. For release preparation,
   include its summary in the release checklist.
4. Set category budgets after Phase 1 establishes a trustworthy baseline. The
   first target is a materially smaller installed Desktop build, with a proposed
   guardrail of no regression above the `v4.0.2` 692.76 MiB baseline and a
   planned reduction of at least 15% before calling the initiative complete.
5. Retain the final content-root marker for manual testing and store publishing.
   Make cleanup of `backend_dist` and other intermediate outputs an explicit
   opt-in post-build action, so local investigation remains possible without
   confusing transient workspace size with release size.

## Validation Matrix

| Change | Required validation |
| --- | --- |
| Staging manifest or package script | GitHub package contract tests, Desktop package contract tests, clean-tree build, and generated size report. |
| Image/media conversion | Production frontend build, image dimension/format checks, desktop visual QA for every affected asset family, and manual race/realm rendering review. |
| BGM conversion | Frontend tests for playlist paths, browser playback smoke test, desktop playback test, and A/B listening approval. |
| Static deduplication | Frozen backend startup, `/api/health`, new game, save/load, configuration loading, and both GitHub and Desktop smoke tests. |
| Electron locale pruning | Desktop launch under each enabled application locale; verify language selection, fallback behavior, and no missing Chromium resource error. |
| PyInstaller dependency removal | Fresh runtime-only build environment, server health check, representative simulation, save/load, LLM test mode, and Desktop smoke test. |

## Acceptance Criteria

1. Every file over the agreed review threshold has a recorded category and
   runtime-usage decision.
2. GitHub and Desktop use the same release-resource manifest for common content.
3. No documentation-only media, unintended bundled save, source media, logs,
   sensitive configuration, or duplicate `static/` tree remains in a release
   artifact.
4. All enabled application locales, splash flow, music, core gameplay assets,
   new game, save/load, and backend health checks pass in packaged builds.
5. The size report shows the installed desktop package is at least 15% below the
   `v4.0.2` baseline, or records why a specific retained runtime asset prevents
   that target.
6. GitHub ZIP size, desktop unpacked size, and any future installer size are
   reported as separate metrics.

## Risks and Decisions Required During Implementation

1. Lossy conversion can damage pixel art or visual identity; approvals must use
   in-game renderings, not only automated file-size measurements.
2. Moving originals changes contributor workflow. The implementation must decide
   whether originals belong in Git LFS, an external asset archive, or a
   repository source-media directory excluded from release staging.
3. Locale pruning must track `static/locales/registry.json`; adding a supported
   UI language must update both the application registry and Electron locale
   allow-list.
4. The current 15% target is a planning guardrail, not a justification for
   removing visible content. Larger reductions should be evaluated only after
   Phase 2 quality checks.
