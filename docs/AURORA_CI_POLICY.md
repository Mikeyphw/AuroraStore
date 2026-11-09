# AuroraStore — lightweight CI and periodic full-qualification gates

> **Migration note:** This CI policy is the temporary R3C+ workflow policy. The normal
> Foundation/R1D/R2D jobs are **not deleted**. Only their automatic triggers are
> removed. Keep their existing `workflow_dispatch` entry points.

## Rules

| Event | CI behavior |
| --- | --- |
| Every PR update | `Aurora — Targeted CI`: scope-selected Python source/security tests |
| Kotlin, Android or Gradle changes | Additional hosted vanillaDebug app + androidTest compilation, **no emulator/release** |
| Every master push | Lightweight targeted check plus gate router |
| Every 5 master integration commits (default) | Full Foundation, R1D and R2D, all jobs, exact SHA |
| Workflow, installer verification/signing, Room migration or build-system change | Immediate full gate on merge |
| Manual gate request / release candidate | Manually dispatch `Aurora — Periodic Full Gate Router` on `master`, forces full gate |

The cadence is `AURORA_FULL_GATE_INTERVAL` GitHub Actions repository variable,
integer 1..25, **default 5**. Configure it under Settings → Secrets and variables
→ Actions → Variables. Counting conservatively treats **one first-parent master
commit as one overlay unit**. A squash merge normally counts once; unrelated
master commits may cause early gates. Do not claim exact per-artifact accounting
when a PR combines multiple overlays. Do not bypass scheduled gates by rebasing
or rewriting published master history.

The last completed full gate is an **immutable tag** `aurora-full-gate/<router_run_id>`
pointing to the exact qualified SHA. Tags are created **only after** all six
Foundation, two R1D and two R2D mandatory jobs pass (10 jobs total). The
initial confirmed full-gate baseline is `6c1de393d0f9df15c4d70b58b0b24e211c480a80`.
The router requires any later checkpoint tag to exist on the *first-parent
master history*. It refuses to certify if master moves during execution.

## Safety and limitations

- A routine successful targeted PR does **not** claim emulator, release, physical
  device, live Play or comprehensive full CI qualification.
- Gate status is post-merge at the exact master SHA; required checks for releases
  must include the latest full gate, not just a targeted PR check. Manual release
  certification is **always** required after a new master SHA, regardless of count.
- Every high-risk source change must go through a full gate after merge; a failed
  or incomplete gate leaves **no checkpoint tag**. No automatic retry that
  silently hides source defects, and no auto-merge.
- Host GitHub Actions executes all Gradle, SDK and emulator tasks; Termux uses
  native Devtool plus lightweight Python source checks only.
- This policy does not solve non-code CI infrastructure failures; full-gate
  check verifies every mandatory job, not only the GitHub workflow conclusion.
- A PR that installs this policy can still trigger the *old* auto-full workflows
  once before its own changes are merged. This is transitional and expected.

## Application and rollback

Apply the consolidated source-pinned schema-v2 overlay through native Devtool;
push the resulting feature branch and watch the `Aurora — Targeted CI` PR run.
The legacy workflows become manual gate workflows **only after this policy PR
has been merged**. Never mark a policy PR green merely because targeted checks
have no Android tasks; require all applicable checks.

To reverse the policy, revert the CI-policy commit / PR in a separate Devtool
overlay, restore the three workflow auto-triggers and remove the temporary
`aurora-targeted.yml`, `aurora-gate-router.yml` and policy scripts. Retain
historical immutable full-gate tags for provenance. Do not treat a bypassed
or unrun full gate as release qualification.

To force a gate from Termux, after the policy merges:

```zsh
gh workflow run aurora-gate-router.yml --repo Mikeyphw/AuroraStore-Standalone --ref master
```

To inspect the newest gate:

```zsh
gh run list -R Mikeyphw/AuroraStore-Standalone \
  --workflow aurora-gate-router.yml --limit 5
```

## New Devtool overlay launcher contract

Future overlay launchers must keep native `devtool validate-overlay` and
`devtool apply-overlay`, automatic non-force `git push`, PR creation and PR
watching. **Do not copy C03 HF02's legacy loop** that explicitly dispatches
all three full workflows on every feature SHA. For routine overlays, the
watch target is the `Aurora — Targeted CI` PR run associated with the final
feature SHA. Keep the PR open if targeted tests fail or no exact-SHA run is
found. Never treat "no checks reported" as pass.

Only the master-only gate router may dispatch the full Foundation/R1D/R2D
workflows on cadence or high-risk changes. An operator may force an independent
manual full-gate run when needed. Automatic PR-watching does not grant
permission to auto-merge or skip failing targeted results.
