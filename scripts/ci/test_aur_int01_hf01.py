#!/usr/bin/env python3
"""Regression of the exact integration compile omissions and hosted retry behavior.

The Gradle executable is a synthetic fixture, never the actual build wrapper.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
KOTLIN = ROOT / 'app/src/main/java/com/aurora/store'
RETRY = ROOT / 'scripts/ci/aurora-hosted-gradle-retry.sh'
AGP = "Plugin [id: 'com.android.application', version: '9.4.1', apply: false] was not found"

class Hotfix(unittest.TestCase):
    def test_merge_imports(self):
        for rel, imports in {
            'compose/ui/commons/ExpandedStreamBrowseScreen.kt': ('androidx.compose.foundation.layout.Arrangement', 'androidx.compose.ui.res.dimensionResource'),
            'compose/ui/commons/StreamBrowseScreen.kt': ('androidx.compose.foundation.layout.Arrangement', 'androidx.compose.ui.res.dimensionResource'),
            'compose/ui/dev/DevProfileScreen.kt': ('androidx.compose.foundation.layout.Arrangement',),
            'compose/ui/updates/UpdatesScreen.kt': ('androidx.compose.ui.res.dimensionResource',),
            'viewmodel/details/AppDetailsViewModel.kt': ('com.aurora.store.data.model.ExodusTracker',),
        }.items():
            source = (KOTLIN / rel).read_text()
            for name in imports:
                self.assertEqual(source.splitlines().count('import ' + name), 1, (rel, name))
        self.assertIn('data class ExodusTracker(', (KOTLIN / 'data/model/Exodus.kt').read_text())
        self.assertIn('Map<Int, ExodusTracker>', (KOTLIN / 'viewmodel/details/AppDetailsViewModel.kt').read_text())

    def test_import_marker_reorder_not_bypass(self):
        from r4_p14_p01_source_contract import production_marker_present
        expected = 'import com.aurora.store.AuroraApp\nimport com.aurora.store.data.catalog.CatalogJourneyGateway\n'
        reordered = 'import com.aurora.store.AuroraApp\nimport com.aurora.store.R\nimport com.aurora.store.data.catalog.CatalogJourneyGateway\n'
        self.assertTrue(production_marker_present(reordered, expected))
        self.assertFalse(production_marker_present(reordered.replace('import com.aurora.store.data.catalog.CatalogJourneyGateway', '// import com.aurora.store.data.catalog.CatalogJourneyGateway'), expected))
        self.assertFalse(production_marker_present(reordered.replace('CatalogJourneyGateway', 'OtherGateway'), expected))
        self.assertFalse(production_marker_present('other.appDetails(packageName)', 'catalogJourneyGateway.appDetails(packageName)'))

    def test_readonly_provider(self):
        p = ROOT / 'app/src/debug/java/com/aurora/store/data/artifact/ArtifactP02SignedFileProvider.kt'
        self.assertIn('    override fun update(\n        uri: Uri,\n        values: ContentValues?,\n        selection: String?,\n        selectionArgs: Array<out String>?\n    ): Int = throw UnsupportedOperationException("Fixture is read-only")', p.read_text())

    def exercise(self, outputs, codes, host=True, expected=0, attempts=1):
        with tempfile.TemporaryDirectory(prefix='aur-int01-retry-fixture-') as tmp:
            folder = Path(tmp)
            (folder / 'bin').mkdir()
            wrapper = folder / 'gradlew'
            wrapper.write_text('#!/usr/bin/env python3\nfrom pathlib import Path\nimport sys\np=Path("count")\nn=int(p.read_text()) if p.exists() else 0\np.write_text(str(n+1))\nassert sys.argv[1:]==["--no-daemon",":app:assembleVanillaDebug"]\nprint(' + repr(outputs) + '[n])\nsys.exit(' + repr(codes) + '[n])\n')
            wrapper.chmod(0o700)
            sleep = folder / 'bin/sleep'
            sleep.write_text('#!/bin/sh\nexit 0\n')
            sleep.chmod(0o700)
            env = {**os.environ, 'GITHUB_ACTIONS': 'true' if host else 'false', 'RUNNER_OS': 'Linux', 'RUNNER_TEMP': tmp, 'PATH': str(folder / 'bin') + ':' + os.environ['PATH']}
            p = subprocess.run(['bash', str(RETRY), '--no-daemon', ':app:assembleVanillaDebug'], cwd=tmp, env=env, text=True, capture_output=True, timeout=20)
            self.assertEqual(p.returncode, expected, p.stdout + p.stderr)
            count = folder / 'count'
            self.assertEqual(int(count.read_text()) if count.exists() else 0, attempts)
            self.assertFalse(list(folder.glob('aurora-gradle-retry.*')))

    def test_retry_then_success(self):
        self.exercise([AGP, 'success'], [1, 0], attempts=2)

    def test_exhaustion(self):
        self.exercise([AGP] * 3, [17] * 3, expected=17, attempts=3)

    def test_compiler_failure_no_retry(self):
        self.exercise(['e: unresolved reference'], [23], expected=23)

    def test_mixed_failure_no_retry(self):
        self.exercise([AGP + '\nExecution failed for task'], [19], expected=19)

    def test_host_only(self):
        self.exercise([], [], host=False, expected=2, attempts=0)

    def test_workflow_wiring(self):
        for workflow in ('aurora-r1d-emulator.yml', 'aurora-r4-p13b-integrated.yml'):
            text = (ROOT / '.github/workflows' / workflow).read_text()
            self.assertEqual(text.count('bash scripts/ci/aurora-hosted-gradle-retry.sh'), 1)
        self.assertIn('python3 -B scripts/ci/test_aur_int01_hf01.py', (ROOT / '.github/workflows/aurora-targeted.yml').read_text())

if __name__ == '__main__':
    unittest.main(verbosity=2)
