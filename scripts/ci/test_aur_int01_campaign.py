#!/usr/bin/env python3
"""Source-level integration routing contract; no Gradle, network or device calls."""
from pathlib import Path
import json
import subprocess
import unittest
import check_aur_int01 as campaign

ROOT=Path(__file__).resolve().parents[2]

class Campaign(unittest.TestCase):
    def test_required_ci_policy(self):
        p=json.loads((ROOT/'config/delivery-required-ci.json').read_text())
        self.assertEqual(p,{'schema_version':1,'repository':'Mikeyphw/AuroraStore',
                         'base_branch':'master','event':'pull_request',
                         'required_workflows':[{'name':'Aurora — Targeted CI','workflow_id':420279514}],
                         'release_qualification':'separate'})
    def test_hosted_routes(self):
        for name in ('aurora-foundation','aurora-r1d-emulator','aurora-r2d-install-emulator'):
            s=(ROOT/'.github/workflows'/f'{name}.yml').read_text()
            self.assertIn('branches: ['+campaign.BRANCH+']',s)
        for name,_ in campaign.LANES.values():
            s=(ROOT/'.github/workflows'/f'aurora-r4-{name}.yml').read_text()
            self.assertIn('      - '+campaign.BRANCH+'\n',s)
        for name in ('aurora-r3d-p03-disposable','aurora-r3d-p04-recovery'):
            s=(ROOT/'.github/workflows'/f'{name}.yml').read_text()
            triggers=s.split('on:\n',1)[1].split('\npermissions:',1)[0]
            self.assertNotIn('  push:',triggers)
            self.assertNotIn('  pull_request:',triggers)
            self.assertIn('workflow_dispatch:',triggers)
    def test_ksp_export_and_provenance_order(self):
        s=(ROOT/'.github/workflows/aurora-targeted.yml').read_text()
        for marker in ('test -s "$schema"','test_aur_int01_room.py --generated "$schema"','git ls-files --others --exclude-standard -- app/schemas/','aurora-room-v17-${{ needs.scope.outputs.head_sha }}'):
            self.assertLess(s.index(marker),s.index('r3c07_hf03_apk_pair.py publish'))
        self.assertIn('if: github.event_name == \'pull_request\'',s.split('name: Verify, sign-check and seal exact-SHA targeted Android APK pair',1)[1])
    def test_no_unmerged_inputs(self):
        for sha in campaign.INPUTS.values():
            subprocess.run(['git','merge-base','--is-ancestor',sha,'HEAD'],cwd=ROOT,check=True)

if __name__=='__main__':unittest.main(verbosity=2)
