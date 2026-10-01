# Version 1.0.0 verification

The final v1 preparation checks passed on 2026-10-01. Application and test code
were verified at `7b246cf`, the versioning checkpoint. This completion record and
the release-note status update are documentation changes.

Release tagging and publishing remain pending. The user explicitly requested no
push until instructed.

## Results

| Check | Result | Scope |
| --- | --- | --- |
| Default regression suite | 306 passed; 12 opt-in checks skipped; 32.91s | Algorithms, exact OPT and finite bounds, native parity, reproducibility, reporting, accounts, Builder runtime, queue, CLI/web integration and saved evidence. |
| Actual Builder isolation suite | 6 passed; 39.67s | Five opt-in container checks plus the ordinary frozen-content/domain check. Kernel controls, physical execution, paired serial/parallel runs, immutable revisions/reruns, trace limits, cancellation, queue recovery and time/output budgets. |
| Real Chromium workflows | 7 passed; 57.81s | Experiment lifecycle and plots, registration/account management, shared navigation, graph editing/wiring, isolated previews, availability, paired runs and frozen trace playback; desktop and 390px layouts. |
| Fresh CMake Release build | Passed | Native DNF/harmonic and both historical reference targets; GCC 14.2.0 and CMake 4.4.3. |
| Installed wheel | Passed | Version metadata, console/Hydra entry points, packaged resources, paired serial/parallel results, native float64/integer execution, provenance, plots/exports, frozen file reruns and initial administrator setup with scrypt hashes. |
| Source/wheel builds | Passed | Version 1.0.0 artifacts; public setup/native/configuration/test-support files included, local agent context and generated research data excluded. |
| Static checks | Passed | Ruff across `src`/`tests`, syntax for all five dashboard JavaScript files, documentation links/anchors and Git whitespace checks. |

All twelve skipped opt-ins from the default suite were subsequently executed:
five actual-container checks and seven browser workflows. The isolation suite's
sixth test is already part of the default suite, so these counts overlap.

The host used Python 3.11.16. Chromium ran in the existing browser-dependency image
with the freshly built 1.0.0 wheel installed, without importing the checkout.
Builder browser requests used a temporary host QA service with separate accounts
and experiment storage; its custom programs used the current rootless runtime.
The installed CLI checks also ran outside the checkout, offline, using the wheel
and freshly compiled native executable. They verified saved source/binary hashes
and package version 1.0.0 in completed experiment manifests.

The primary verifier personally inspected desktop/phone screenshots of Builder,
verification playback, account management, sign-in and result plots. Browser
workflows reported no page errors. A read-only test mount prevented writing the
optional pytest cache; this produced one warning without affecting test results.
No application fix was needed during the release pass.

## Reproducing the checks

Install the development/browser extras and follow the
[Builder runtime setup](BUILDER.md#local-setup). Browser execution needs Chromium
and its system libraries; the [development guide](../README.md#development)
describes the browser test image. Run from the source checkout with Python 3.11:

```sh
pytest -q
ruff check src tests
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 2
BINCOVERING_ISOLATION=1 pytest tests/test_builder_integration.py -q
BINCOVERING_BROWSER=1 BINCOVERING_BUILDER_ISOLATION=1 pytest tests/test_browser.py tests/test_accounts_browser.py tests/test_builder_browser.py -q
python -m build --no-isolation
```

For Chromium in a separate test container, provide `BINCOVERING_BUILDER_URL` and
ephemeral account credentials for a host QA server, as described in
[Builder verification](BUILDER.md#verification-commands). The browser container
does not receive a container-engine socket. Install the built wheel there and
run from a directory outside the checkout to verify packaged behavior.

Installed-package verification should exercise `bincovering algorithms`, a small
Hydra run with multiple workers, saved-result inspection, Python/native pairs in
both domains, plot/export, rerun of frozen file input and `setup-admin`. Check
that completed manifests report version 1.0.0 and preserve input/source/binary
evidence. Compare serial and parallel results by trial identity, excluding timing.

Local scripts, screenshots, temporary account/experiment data and build artifacts
are retained under ignored `outputs/v1-release-validation/`. They are verification
evidence, not researcher input or release assets tracked in Git.

These bounded checks validate the current implementation. The exact-arithmetic
assumptions and remaining advice/reproduction research limitations in the
[guarantees](algorithms/GUARANTEES.md) and [release notes](RELEASE_NOTES.md) still apply.
