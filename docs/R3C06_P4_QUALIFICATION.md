# R3C06 P4 — API36 measured acceptance (read-only first)

**Scope:** qualification support on top of R3C06 P3 HF01. Does not change app
production APK verification or Play evidence, and does not grant publisher
trust to APKM/XAPK metadata. Do not equate source compilation with device proof.

## Changes

1. Source-bound read-only acceptance receipt over **eight device suites / 51
   executed test methods**, with exact test counts and a SHA-256 digest for
   each hosted instrumentation log. Any missing/duplicate pass line, error marker,
   absent source/run identity or wrong API refuses qualification. The receipt
   explicitly disclaims real installation, bundletool, vendor formats and release.
2. `r3c06_bundletool_matrix.py` now treats only *successful signed selections*
   with materially different APK output as device-dimension coverage. A refused
   selection can never satisfy the ABI/density/locale/SDK dimension.
3. `r3c06_api36_live_install.py` no longer treats an ADB package query error as
   package absence, and only accepts the test fixture label when owned by the
   system installer package. It requires `GITHUB_SHA` matching the checked-out
   source before producing a qualified installation receipt. All existing
   explicit opt-in and cleanup requirements remain.
4. Stock-Python negative tests run from the existing targeted source gate.

## Run the existing hosted API36 read-only gate

Only after this overlay's targeted CI is green, manually dispatch the existing
R1D API36 workflow on PR #9's exact feature branch. This is intentionally **not**
run by the overlay launcher:

```zsh
cd ~/Code/AuroraStore-Standalone
# Manual action; check the PR SHA before and after the workflow.
gh workflow run aurora-r1d-emulator.yml \
  --repo Mikeyphw/AuroraStore-Standalone \
  --ref feature/r3c04-c02-c08-import-handoff-archives-20261109
```

Check the newly-created run on GitHub and download its `aurora-r1d-api36-emulator-evidence`
artifact. The R3C06 read-only receipt is placed at:

`aurora-r3c03-c02/R3C06_P4_API36_READONLY_RECEIPT.json`

Its `overall=PASS` is **not** proof of actual installation. Verify
`source_sha` equals the *current* PR head, not an earlier branch commit.

## Deliberately separate acceptance: real install and bundletool

`r3c06_api36_live_install.py` only runs when `R3C06_ALLOW_LIVE_INSTALL=yes`
inside an explicitly controlled API36 emulator. It creates/removes only the
synthetic fixture package, requires a verified system confirmation, executes
both reject and accept scenarios, verifies the installed signer, and refuses
on incomplete cleanup. Never call it from ordinary PR targeted CI or a physical
phone. Its own receipt must say `overall=PASS` to count. **This patch does not
run it automatically.**

The bundletool oracle requires an actual `.aab`, a SHA-256-pinned genuine
bundletool JAR, and a configured emulator. It must return `overall=PASS` with
all requested dimensions truly covered by *signed* extracted selections to
qualify that specific AAB. `PARTIAL` and `REFUSED` are not proof of full
compatibility. Neither an AAB oracle pass nor synthetic ZIP wrappers prove
real-world vendor archive behavior.

## Roadmap truth

R3C06 remains **partially qualified** until the exact-head API36 evidence,
explicit live installation (if authorized), representative AAB/device targeting,
negative mixed-signer/split fixtures and real vendor APKM/XAPK samples all pass.
R3C07 UX and R3C08 complete signoff remain separate phases. The two complete
roadmap documents are retained unchanged within the delivery ZIP.
