# Aurora R1B HF01 — Hosted ktlint qualification fix

**Repository:** `Mikeyphw/AuroraStore`

**Existing PR:** https://github.com/Mikeyphw/AuroraStore/pull/3

**Expected branch:** `feature/r1b-download-recovery-20261107`

**Pinned PR head:** `c3e5cfbdabd393db4806c34601730b058c7b32ee`

## Failure observed

Both R1B GitHub Actions runs failed in `:app:ktlintMainSourceSetCheck`. The failure lists three DAO function signatures and an extra blank line in `DownloadDao.kt`. The R1A and R1B source checks completed successfully.

## This hotfix

- Reformat `cancelActiveDownload`, `failOrphanedDownload`, and `deleteVersion` on one line each; all three signatures remain at or below the configured 100-character lint limit.
- Remove the extra blank line preceding the retry function documentation.
- Do not modify Android logic, Room SQL, workers, UI, CI configuration, or Gradle dependencies.
- Apply only to the expected branch head and exact original file blob. No force-push, branch reset, or unrelated file edits.
- Re-run foundation, R1A, R1B and HF01 source checks before pushing.

**Qualification still required:** GitHub Actions Kotlin compilation, Android APK assembly, ktlint, JVM tests, and subsequent device tests.

## Termux/Zsh installation

Copy `Aurora_R1B_HF01_Consolidated.zip` to `/sdcard/Download/`, then:

```zsh
DIR="$TMPDIR/aurora-r1b-hf01"
mkdir -p "$DIR"
unzip -oq /sdcard/Download/Aurora_R1B_HF01_Consolidated.zip -d "$DIR"
zsh "$DIR/APPLY_HF01.zsh"
```

After pushing, the existing PR #3 should automatically receive new CI runs.
