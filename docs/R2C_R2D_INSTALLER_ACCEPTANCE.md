# R2C + R2D — installer compatibility and hosted real installation acceptance

## Source baseline and scope

Pinned source commit: `2ebf98c9cfddc5cced43142c8533b1fa2d4dd0ad` (`master`, R2B HF01).

R2C adds correlated privileged/microG results and fail-closed command response handling.
Root and Shizuku must check `pm` create, write and commit responses rather than trusting
an exit code or blindly reading the first output line. Aurora Services now uses a
per-request binder connection, supports both callback ABIs, accepts the first terminal
callback only, and times out rather than hanging. microG results carry the immutable
version/attempt and cannot report success without OS package-version confirmation.

Backend completion emits an attributed candidate event; the production `DownloadHelper`
accepts the result through Room's generation-scoped CAS and confirms Android's actual
installed target version before one-time notification and APK cleanup. Existing native
PackageInstaller receiver CAS remains authoritative for its own direct result handling.

R2D runs an **actual Android PackageInstaller session** on API 36 in GitHub Actions.
It builds and signs an ephemeral fixture APK with a throwaway CI key, then exercises
`pm install-create`, `pm install-write`, and `pm install-commit`. A separate instrumentation
process seeds an interrupted INSTALLING row in Aurora's actual production Room database,
plus another app-owned uncommitted PackageInstaller session. The workflow force-stops Aurora,
commits the system APK, and starts the real production AuroraApp (outside instrumentation)
to trigger its DownloadHelper startup recovery. The following instrumentation process
verifies that Room was ALREADY reconciled by the application; it does not do the recovery
itself. The test also asserts the installed target version and stale-attempt rejection. It also verifies the uncommitted
Aurora-owned session survives process death and can be explicitly abandoned.

### Boundaries — not tested or claimed

- This test uses the real Android package manager, but **does not** complete a user
  approval prompt through Aurora's `SessionInstaller` UI or download APKs from Google Play.
- No live microG instance, Aurora Services privileged server, root grant, or Shizuku
  binder is present in the hosted emulator. Their runtime/device qualification remains
  separate; only code policy/unit and source CI coverage is included here.
- No physical-device, release-signing or release-qualification result is produced.
- API 36 workflow can only be called PASS after a hosted GitHub run succeeds and its
  receipt contains `overall=PASS`. Before then, implementation is unqualified.

## Quality gates

1. `scripts/ci/check_r2c.py`, `check_r2d.py`, and `test_r2d_host_contract.py`
   plus existing R1/R2 contracts. The host tests deliberately fake Android and are NOT
   device acceptance evidence.
2. Foundation CI: `assembleVanillaDebug ktlintCheck testVanillaDebugUnitTest`.
3. Dedicated R2D API 36 emulator workflow with actual APK signing, installation,
   process force-stop and production Room instrumentation, with upload-on-failure receipts.
4. Fail closed on missing fixtures, missing emulator, missing expected instrumentation
   count, non-success package-manager receipts or missing OS-installed version.
