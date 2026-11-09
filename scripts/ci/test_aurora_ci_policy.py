#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline, adversarial tests for Aurora's targeted CI and full-gate state machine."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import aurora_ci_policy as policy


class PlanTests(unittest.TestCase):
    def test_docs_only_does_not_compile_android(self):
        p = policy.classify(['docs/README.md'])
        self.assertFalse(p['needs_android'])
        self.assertIn('check_foundation.py', p['tests'])

    def test_main_kotlin_requires_targeted_android(self):
        p = policy.classify(['app/src/main/java/com/aurora/store/data/room/play/Foo.kt'])
        self.assertTrue(p['needs_android'])
        self.assertIn('check_r3c03_c02.py', p['tests'])

    def test_workflow_changes_run_all_source_contracts(self):
        p = policy.classify(['.github/workflows/aurora-foundation.yml'])
        self.assertTrue(p['ci_sensitive'])
        self.assertIn('test_r2b_sql_cas.py', p['tests'])
        self.assertFalse(p['needs_android'])

    def test_unknown_kotlin_fails_closed_to_all_source_contracts(self):
        p = policy.classify(['app/src/main/java/example/New.kt'])
        self.assertTrue(p['needs_android'])
        self.assertIn('test_r3c03_c01_security.py', p['tests'])

    def test_selected_tests_exist_filter_never_introduces_synthetic_ones(self):
        p = policy.classify(['docs/README.md'], present={'check_foundation.py'})
        self.assertEqual(p['tests'], ['check_foundation.py'])

    def test_installer_runs_security_and_real_fixture_contracts(self):
        p = policy.classify(['app/src/main/java/com/aurora/store/data/installer/Foo.kt'])
        self.assertIn('check_r2d.py', p['tests'])
        self.assertIn('test_r2b_sql_cas.py', p['tests'])


class GateGitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aurora-ci-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q', '-b', 'master')
        self.git('config', 'user.name', 'Aurora CI Test')
        self.git('config', 'user.email', 'ci@example.invalid')
        self.write_commit('README.md', 'base\n')
        self.base = self.git('rev-parse', 'HEAD')
        self.mock_base = patch.object(policy, 'INITIAL_GATE_SHA', self.base)
        self.mock_base.start()
        self.addCleanup(self.mock_base.stop)

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, text=True).strip()

    def write_commit(self, path, content):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
        self.git('add', '--', path)
        self.git('commit', '--quiet', '-m', 'test overlay')
        return self.git('rev-parse', 'HEAD')

    def plan(self, interval=5, force=False):
        return policy.gate_plan(self.git('rev-parse', 'HEAD'), interval, cwd=self.root, force=force)

    def test_not_due_until_fifth_mainline_commit(self):
        for n in range(4):
            self.write_commit(f'docs/{n}.txt', str(n))
        p = self.plan()
        self.assertEqual(p['overlay_units_since_gate'], 4)
        self.assertFalse(p['due'])
        self.write_commit('docs/5.txt', '5')
        self.assertTrue(self.plan()['due'])
        self.assertIn('cadence', self.plan()['reasons'])

    def test_ordinary_installer_changes_wait_for_periodic_gate(self):
        self.write_commit('app/src/main/java/com/aurora/store/data/installer/FeatureGlue.kt', 'data')
        self.assertFalse(self.plan()['due'])

    def test_immediate_risk_gate(self):
        self.write_commit('app/src/main/java/com/aurora/store/data/installer/verification/Trust.kt', 'data')
        p = self.plan()
        self.assertEqual(p['overlay_units_since_gate'], 1)
        self.assertIn('high-risk-change', p['reasons'])

    def test_tag_resets_count_without_rewriting_history(self):
        for n in range(5):
            self.write_commit(f'docs/{n}', str(n))
        old_head = self.git('rev-parse', 'HEAD')
        self.git('tag', 'aurora-full-gate/123', old_head)
        self.assertEqual(self.plan()['overlay_units_since_gate'], 0)
        self.write_commit('docs/next', 'next')
        self.assertEqual(self.plan()['overlay_units_since_gate'], 1)

    def test_non_mainline_gate_tag_cannot_reset_counter(self):
        self.git('checkout', '-q', '-b', 'side')
        side = self.write_commit('docs/side', 'side')
        self.git('tag', 'aurora-full-gate/bogus', side)
        self.git('checkout', '-q', 'master')
        self.write_commit('docs/master', 'master')
        p = self.plan()
        self.assertEqual(p['overlay_units_since_gate'], 1)
        self.assertEqual(p['baseline_sha'], self.base)

    def test_manual_gate_forces_even_without_changes(self):
        p = self.plan(force=True)
        self.assertTrue(p['due'])
        self.assertEqual(p['overlay_units_since_gate'], 0)

    def test_gate_interval_refuses_zero_or_excessive(self):
        for number in (0, 26, -1):
            with self.assertRaises(ValueError):
                self.plan(number)

    def test_diff_rejects_short_sha(self):
        with self.assertRaises(ValueError):
            policy.paths_between('bad', 'bad', cwd=self.root)

    def test_no_missing_baseline_silent_success(self):
        with patch.object(policy, 'INITIAL_GATE_SHA', 'f' * 40):
            with self.assertRaises(RuntimeError):
                self.plan()

    def test_required_jobs_exact_and_nonempty(self):
        self.assertEqual(sum(map(len, policy.EXPECTED_JOBS.values())), 10)
        self.assertEqual(len(policy.EXPECTED_JOBS), 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
