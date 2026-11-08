#!/usr/bin/env python3
"""Exercise R2D host shell contracts without an Android SDK or Gradle.

This is a fake-device *negative/host-contract* test, not Android runtime evidence.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "scripts/ci/r2d_build_fixture.sh"
R3B_FIXTURE = ROOT / "scripts/ci/r3b_build_fixtures.sh"
EMULATOR = ROOT / "scripts/ci/r2d_emulator_ci.sh"


def executable(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\nset -eu\n" + contents)
    path.chmod(0o755)


def check_code(command: list[str], env: dict[str, str], want_success: bool) -> None:
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if (result.returncode == 0) != want_success:
        raise AssertionError(
            f"Unexpected host gate exit={result.returncode}: "
            f"stdout={result.stdout[-2000:]} stderr={result.stderr[-2000:]}"
        )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="aurora-r2d-host-") as temp:
        work = Path(temp)
        sdk = work / "sdk"
        platform = sdk / "platforms/android-37.0/android.jar"
        platform.parent.mkdir(parents=True)
        platform.write_bytes(b"mock Android jar")
        buildtools = sdk / "build-tools/36.0.0"
        toolbin = work / "bin"
        out = work / "aurora-r2d-emulator"
        out.mkdir()

        executable(
            buildtools / "aapt2",
            'while (($#)); do if [[ "$1" == "-o" ]]; then '
            'shift; printf "fixture" > "$1"; break; fi; shift; done\n',
        )
        # The fake apksigner has deterministic v2 AND v3 signer records so
        # the host gate detects an incompletely corrupted signing-block set.
        # This is not a substitute for cryptographic apksigner / Android runtime.
        fake_signer = work / "mock_apksigner.py"
        fake_signer.write_text('''#!/usr/bin/env python3
import os
import struct
import sys
from pathlib import Path

args = sys.argv[1:]
if args and args[0] == "verify":
    if os.environ.get("MOCK_ACCEPT_INVALID_SIGNATURE") == "1":
        print("Verifies")
        sys.exit(0)
    raw = Path(args[-1]).read_bytes()
    expected_signers = 1 if os.environ.get("MOCK_OMIT_V3_SCHEME") == "1" else 2
    if b"APK Sig Block 42" in raw and raw.count(bytes.fromhex("55" * 32)) == expected_signers:
        print("Verifies")
        sys.exit(0)
    print("DOES NOT VERIFY")
    sys.exit(1)
if "--out" not in args:
    sys.exit(2)
out = Path(args[args.index("--out") + 1])
digest = bytes.fromhex("55" * 32)
record = struct.pack("<I", 4 + 4 + len(digest)) + struct.pack("<I", 0x0101) + struct.pack("<I", len(digest)) + digest
signed = struct.pack("<I", len(record)) + record + struct.pack("<I", 0) + struct.pack("<I", 0)
signer = struct.pack("<I", len(signed)) + signed + struct.pack("<I", 0) + struct.pack("<I", 0)
signers = struct.pack("<I", len(signer)) + signer
value = struct.pack("<I", len(signers)) + signers
pair = b"".join(
    struct.pack("<Q", 4 + len(value)) + struct.pack("<I", scheme_id) + value
    for scheme_id in (0x7109871a, 0xf05368c0)
)
if os.environ.get("MOCK_OMIT_V3_SCHEME") == "1":
    pair = struct.pack("<Q", 4 + len(value)) + struct.pack("<I", 0x7109871a) + value
size = len(pair) + 24
block = struct.pack("<Q", size) + pair + struct.pack("<Q", size) + b"APK Sig Block 42"
out.write_bytes(b"mock-signed-fixture" + block + b"zip-central-directory")
''')
        executable(buildtools / "apksigner", 'exec python3 "$MOCK_APKSIGNER" "$@"\n')
        executable(
            toolbin / "keytool",
            'while (($#)); do if [[ "$1" == "-keystore" ]]; then '
            'shift; printf key > "$1"; exit; fi; shift; done\nexit 1\n',
        )
        executable(toolbin / "sleep", 'exit 0\n')

        env = {**os.environ,
               "RUNNER_TEMP": str(work),
               "ANDROID_SDK_ROOT": str(sdk),
               "PATH": str(toolbin) + os.pathsep + os.environ["PATH"],
               "GITHUB_SHA": "test-commit-not-a-real-commit",
               "GITHUB_RUN_ID": "123",
               "GITHUB_RUN_ATTEMPT": "1",
               "MOCK_LOG": str(work / "adb-commands.txt"),
               "MOCK_MODE": "success",
               "MOCK_APKSIGNER": str(fake_signer)}
        check_code(["bash", str(FIXTURE)], env, True)
        assert b"APK Sig Block 42" in (out / "r2d-fixture.apk").read_bytes()
        assert not (out / "r2d-fixture.keystore").exists(), "CI signing key leaked"
        assert not (out / "r2d-fixture-unsigned.apk").exists()
        assert (out / "r2d-fixture.sha256").read_text().split()[0] == hashlib.sha256(
            (out / "r2d-fixture.apk").read_bytes()
        ).hexdigest()
        print("R2D_HOST_PASS: ephemeral signed fixture and signing-key cleanup")
        check_code(["bash", str(R3B_FIXTURE)], env, True)
        r3b = out / "r3b"
        assert len(list(r3b.glob("*.apk"))) == 8
        assert len(list(r3b.glob("*.keystore"))) == 0
        assert len((r3b / "sha256sums.txt").read_text().splitlines()) == 8
        assert (r3b / "tampered-v2-v3.apk").is_file()
        assert (r3b / "tampered-v2-v3-rejection.txt").is_file()
        print("R3B_HOST_PASS: seven positive fixtures, both signature schemes invalid, no leaked keys")
        # Negative gate: a deliberately misbehaving apksigner must never
        # allow an invalid signed digest to become an accepted fixture.
        # Negative fixture runs must never rewrite the known-good fixture set.
        unsafe_env = {
            **env,
            "RUNNER_TEMP": str(work / "negative-accept"),
            "MOCK_ACCEPT_INVALID_SIGNATURE": "1",
        }
        unsafe = subprocess.run(
            ["bash", str(R3B_FIXTURE)], cwd=ROOT, env=unsafe_env,
            capture_output=True, text=True, timeout=30, check=False,
        )
        assert unsafe.returncode != 0
        assert "R3B_REFUSED: corrupt v2+v3 fixture incorrectly passed apksigner" in unsafe.stderr
        print("R3B_HOST_REFUSAL_PASS: false-positive cryptographic verifier")
        # A tool that silently signs v2 alone must also be refused: otherwise
        # this test would reproduce the original API36 fallback mistake.
        missing_v3 = subprocess.run(
            ["bash", str(R3B_FIXTURE)], cwd=ROOT,
            env={
                **env,
                "RUNNER_TEMP": str(work / "negative-missing-v3"),
                "MOCK_OMIT_V3_SCHEME": "1",
            },
            capture_output=True, text=True, timeout=30, check=False,
        )
        assert missing_v3.returncode != 0
        assert "R3B_TAMPER_REFUSED: need v2 and v3 signers" in missing_v3.stderr
        print("R3B_HOST_REFUSAL_PASS: missing v3 scheme")

        executable(toolbin / "adb", '''printf '%s\\n' "$*" >> "$MOCK_LOG"
if [[ "$1" == "install" || "$1" == "push" ]]; then echo Success; exit 0; fi
if [[ "$1" == "logcat" ]]; then echo 'Production restart log'; exit 0; fi
if [[ "$1" != "shell" ]]; then exit 1; fi
shift
if [[ "${1:-}" == "-T" ]]; then shift; fi
case "$*" in
  'getprop ro.build.version.sdk') echo 36 ;;
  'pm list instrumentation') echo 'instrumentation:com.aurora.store.debug.test/com.aurora.store.HiltInstrumentationTestRunner (target=com.aurora.store.debug)' ;;
  'am instrument'* )
    if [[ "$MOCK_MODE" == 'instrumentation_failure' ]]; then
      echo 'FAILURES!!! Tests run: 1, Failures: 1'
    else
      echo 'OK (1 test)'
    fi ;;
  'am force-stop'* ) ;;
  'run-as com.aurora.store.debug mkdir'* ) ;;
  'run-as com.aurora.store.debug cp'* ) ;;
  'rm -f /data/local/tmp/'* ) ;;
  'am start -W -n'* )
    if [[ "$MOCK_MODE" == 'startup_failure' ]]; then echo 'Error: app did not start'
    else echo 'Status: ok'; fi ;;
  'pm install-create'* ) echo 'Success: created install session [314]' ;;
  'pm install-write'* ) echo Success ;;
  'pm install-commit'* )
    if [[ "$MOCK_MODE" == 'commit_failure' ]]; then echo 'Failure [INSTALL_FAILED_INVALID_APK]'
    else echo Success; fi ;;
  'pm install-abandon'* ) echo Success ;;
  'dumpsys package'* )
    if [[ "$MOCK_MODE" == 'missing_version' ]]; then echo 'versionCode=72'
    else echo 'versionCode=73 minSdk=23'; fi ;;
  *) echo "unrecognized fake adb: $*" >&2; exit 2 ;;
esac
''')
        (ROOT / "app/build/outputs/apk/vanilla/debug").mkdir(parents=True, exist_ok=True)
        (ROOT / "app/build/outputs/apk/androidTest").mkdir(parents=True, exist_ok=True)
        app_apk = ROOT / "app/build/outputs/apk/vanilla/debug/r2d-mock-vanilla.apk"
        test_apk = ROOT / "app/build/outputs/apk/androidTest/r2d-mock-androidtest.apk"
        if list(app_apk.parent.glob("*.apk")) or list(test_apk.parent.glob("*.apk")):
            raise RuntimeError("Mock test refuses to overwrite real APK outputs")
        app_apk.write_bytes(b"mock app")
        test_apk.write_bytes(b"mock androidTest")
        try:
            check_code(["bash", str(EMULATOR)], env, True)
            receipt = json.loads((out / "R2D_INSTALL_LIFECYCLE_RECEIPT.json").read_text())
            assert receipt["overall"] == "PASS"
            commands = (work / "adb-commands.txt").read_text()
            for expected in (
                "pm install-create", "pm install-write", "pm install-commit",
                "am force-stop com.aurora.store.debug",
                "am start -W -n com.aurora.store.debug/com.aurora.store.ComposeActivity",
            ):
                assert expected in commands, expected
            for mode in (
                "instrumentation_failure", "commit_failure",
                "missing_version", "startup_failure"
            ):
                env["MOCK_MODE"] = mode
                check_code(["bash", str(EMULATOR)], env, False)
                print(f"R2D_HOST_REFUSAL_PASS: {mode}")
        finally:
            app_apk.unlink(missing_ok=True)
            test_apk.unlink(missing_ok=True)
        print("R2D_HOST_CONTRACT_PASS: 1 positive, 4 negative device-script cases")


if __name__ == "__main__":
    main()
