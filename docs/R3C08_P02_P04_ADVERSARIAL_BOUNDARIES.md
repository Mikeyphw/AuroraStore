# AuroraStore R3C08 P01 HF04 + P02–P04 consolidated adversarial acceptance

## Source and stage

This is one additive, exact-source, native Devtool schema-v2 delivery on PR #9,
starting from commit `46288a20dfb1591717e6d86d275a9e1522599685`.
R3C07 and R3C08 P01 previously authored app code is unchanged. The historical
P01 API 36 run `43133857427` performed all three actual tests, but its
original receipt checker incorrectly expected one `test=` event per method.
**HF04 requires ordered AndroidJUnitRunner start (code 1) and finish (code 0)**
for every one of the three methods, plus its independent grant-status report.
The actual prior log is bundled for independent parser regression, but no new
source SHA can be qualified solely from that historical execution.

## P02 — cancellation, failure and private cleanup

- API 36 device tests invoke actual one-shot stream cancellation and verify
  that a cancelled lease cannot be reused or revived.
- Direct private staging with a pre-cancelled token and with cancellation
  while reading a file must fail and leave no new staging child directories.
- Controlled Android provider open failure must not leave private cache
  output or enable the unverified installation action.
- **A deliberately killed, test-APK-only provider is tested for distinct-PID
  recovery, but arbitrary third-party provider crashes and timing attacks are
  NOT qualified by these twenty-one tests.** Isolated test-provider
  process-death is exercised here, but arbitrary third-party provider crashes
  and timing races remain in R3C08 P05.

## P03 — adversarial archive/signed set

- ZIP traversal is rejected by the actual pre-index bounds reader.
- Unsigned byte input is staged and then rejected by the production verifier.
- Contradictory unsigned XAPK metadata and incomplete APKM metadata cannot
  override signed Android identity.
- Competing ABI targeting and duplicate signed split names are rejected, never
  auto-selected. The inherited R3C06 signed archives and 51-case API36 suite
  remain part of the same R1D workflow.
- This is a bounded set of adversarial tests; it is not a general-purpose
  formal proof of every archive mutation.

## P04 — source/Play independence and installer preconditions

- User consent cannot override a missing signature or mismatched installed signer.
- Browser/source-selection claims cannot mint an authenticated publisher or
  Google Play delivery receipt.
- Installation approval, downgrade consent and unknown-publisher consent are
  independent requirements.
- The default suite is deliberately **non-installing**. Its Android package
  inventory is captured before and after and must match, with a cryptographic
  digest in the as-run receipt.
- **Actual OS installer DENY→ACCEPT, rollback, preserved app data and package
  history remain separately opted-in R3C07 P04 / R3C08 P05 acceptance gates.**
  A source-only consent test is never called a real installer rollback test.

## Qualification gate

1. Targeted PR CI has three successful jobs at the new exact Git commit.
2. GitHub-hosted R1D API 36 is dispatched with all manual installer,
   TalkBack, bundletool and feature toggles false.
3. The historical P01 three-test receipt and new P02–P04 twenty-one-test receipt
   must be generated on the **same new source SHA and GitHub run ID**, from
   real Android instrumentation logs.
4. P02–P04 must have exactly twenty-one selected methods, one Android start and
   completion per method, one final success, a bounded log and unchanged app
   inventory; require an isolated-provider PID start/kill/restart trace,
   as-run evidence artifact and reconstruction.
5. Preserve existing R3C06/R3C07 independent source/run-bound receipts.
6. No release, physical-device, vendor, verified publisher, arbitrary real third-party provider
   process-death, or actual OS rollback claims result from this phase.

P05 remains a distinct final adversarial signoff and may require additional
source changes discovered in actual hosted instrumentation.

### P03 audited expansion (folded)

Five additional Android instrumented tests extend P03 beyond the original
three: a real STORED ZIP local-header CRC mismatch and private-staging cleanup;
a tampered EOCD central-directory extent and cleanup; cyclic, missing and
self-referential signed feature dependencies (with a valid counterexample);
a signed-manifest/platform identity disagreement and historical-only signer
status; and unsupported ABI/orphan configuration splits. All are read-only,
fail-closed tests invoking the production policies. No signer identity,
publisher provenance or real install success is inferred from these outcomes.
The expanded P02-P04 host suite requires exactly 16 instrumentation tests.

**Still unqualified:** APK v2/v3 cryptographic penetration against third-party
malformed packages and verified live install/rollback across devices; these
remain P05/manual acceptance and cannot be claimed by the source audit.

### P04 audited expansion (folded)
Five independent read-only Android checks were added to the original three P04
cases: synthetic verified-import objects cannot mint official publisher/Play
proof; browser attribution expires or becomes invalid after source/URL changes;
APKPure attribution needs both a fresh opt-in and alternative approval;
inconsistent installed signing identity and missing distinct consent remain
fail-closed; and every terminal Android session-receipt state rejects
success/rejection replay. Synthetic imports are policy fixtures, NOT an actual
cryptographically signed install. Package inventory is monitored before/after
but does not prove rollback or preserve app data. Actual OS installer DENY→ACCEPT,
real arbitrary callbacks and rollback remain opted-in P05/manual gates.
The combined suite now has 21 tests (P02 five + P03 eight + P04 eight).
