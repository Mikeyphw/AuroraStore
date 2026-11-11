#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source-level regressions for P6 on-demand title location.

This does NOT replace AGP's compiled-AAB validation: hosted bundleDebug and
bundletool still determine runtime qualification. Fail on misplaced, duplicated,
ambiguous or missing resources without weakening signing/targeting checks.
"""
from __future__ import annotations
import os
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

TITLE_NAME='r3c06_feature_title'
TITLE='@string/'+TITLE_NAME
DIST='{http://schemas.android.com/apk/distribution}'
ROOT=Path(__file__).resolve().parents[2]
DEFAULT=ROOT/'scripts/ci/fixtures/r3c06_feature_bundle'

class InvalidTitle(ValueError):
    pass

def check_resources(base_xml: str, feature_xml: str, feature_strings_xml: str|None):
    """A real feature title must live only in the base module resource table."""
    try:
        root=ET.fromstring(base_xml)
        feature=ET.fromstring(feature_xml)
        feature_resources=ET.fromstring(feature_strings_xml) if feature_strings_xml is not None else None
    except ET.ParseError as exc:
        raise InvalidTitle('malformed fixture resource/manifest XML') from exc
    if root.tag!='resources':raise InvalidTitle('base title file must be <resources>')
    selected=[n for n in root if n.tag=='string' and n.get('name')==TITLE_NAME]
    if len(selected)!=1 or not (selected[0].text or '').strip():
        raise InvalidTitle('exactly one nonempty module title required in BASE')
    mod=feature.find(DIST+'module')
    if mod is None or mod.get(DIST+'title')!=TITLE:
        raise InvalidTitle('feature module must reference exact BASE title')
    delivery=mod.find(DIST+'delivery')
    if delivery is None or delivery.find(DIST+'on-demand') is None or \
       delivery.find(DIST+'install-time') is not None:
        raise InvalidTitle('must remain on-demand, never install-time')
    fuse=mod.find(DIST+'fusing')
    if fuse is None or fuse.get(DIST+'include')!='false':
        raise InvalidTitle('fixture feature must not fuse')
    if feature_resources is not None:
        # A stub is allowed for Devtool modify-only transactions, but it MUST
        # contain no resources of its own. Merely leaving the original title
        # in the feature would still cause the hosted packaging failure.
        if feature_resources.tag!='resources' or feature_resources.attrib or list(feature_resources):
            raise InvalidTitle('feature resource stub must be empty and contain no title')
    return True

def verify_feature_title(fixture: Path):
    fixture=Path(fixture)
    base=fixture/'app/src/main/res/values/strings.xml'
    feature=fixture/'featureproof/src/main/AndroidManifest.xml'
    old=fixture/'featureproof/src/main/res/values/strings.xml'
    if not base.is_file() or base.is_symlink() or not feature.is_file() or feature.is_symlink():
        raise InvalidTitle('base title or feature manifest absent/unsafe')
    if not old.is_file() or old.is_symlink():
        raise InvalidTitle('feature module must contain a safe inert resource stub')
    return check_resources(base.read_text(encoding='utf-8'),
                           feature.read_text(encoding='utf-8'),old.read_text(encoding='utf-8'))

GOOD_BASE='<?xml version="1.0" encoding="utf-8"?>\n<!-- SPDX-License-Identifier: GPL-3.0-or-later -->\n<resources><string name="r3c06_feature_title">R3C06 synthetic dynamic feature</string></resources>\n'
GOOD_EMPTY='<?xml version="1.0" encoding="utf-8"?>\n<resources/>\n'
GOOD_FEATURE='<?xml version="1.0" encoding="utf-8"?>\n<!-- SPDX-License-Identifier: GPL-3.0-or-later -->\n<manifest xmlns:android="http://schemas.android.com/apk/res/android"\n          xmlns:dist="http://schemas.android.com/apk/distribution">\n    <dist:module dist:title="@string/r3c06_feature_title">\n        <dist:delivery><dist:on-demand /></dist:delivery>\n        <dist:fusing dist:include="false" />\n    </dist:module>\n    <application />\n</manifest>\n'

class TitleLocationNegatives(unittest.TestCase):
    def test_real_fixture_title_is_in_base_only(self):
        actual=Path(os.environ.get('R3C06_P6_FIXTURE_ROOT',str(DEFAULT)))
        self.assertTrue(verify_feature_title(actual))
    def test_valid_synthetic_base_feature(self):
        self.assertTrue(check_resources(GOOD_BASE,GOOD_FEATURE,GOOD_EMPTY))
    def test_reject_missing_feature_stub(self):
        fixture=Path(os.environ.get('R3C06_P6_FIXTURE_ROOT',str(DEFAULT)))
        with tempfile.TemporaryDirectory(prefix='p6-title-absent-') as temp:
            from shutil import copytree
            copytree(fixture,Path(temp)/'fixture')
            (Path(temp)/'fixture/featureproof/src/main/res/values/strings.xml').unlink()
            with self.assertRaises(InvalidTitle):
                verify_feature_title(Path(temp)/'fixture')

    def test_reject_nonempty_feature_stub(self):
        with self.assertRaises(InvalidTitle):
            check_resources(GOOD_BASE,GOOD_FEATURE,
                            '<resources><string name="other">Not inert</string></resources>')
        with self.assertRaises(InvalidTitle):
            check_resources(GOOD_BASE,GOOD_FEATURE,'<not-resources/>')

    def test_reject_missing_base_title(self):
        with self.assertRaises(InvalidTitle):
            check_resources('<resources/>',GOOD_FEATURE,None)
    def test_reject_duplicate_base_titles(self):
        doubled=GOOD_BASE.replace('</resources>',
            '<string name="r3c06_feature_title">Duplicate</string></resources>')
        with self.assertRaises(InvalidTitle):check_resources(doubled,GOOD_FEATURE,None)
    def test_reject_feature_only_or_duplicate_title(self):
        with self.assertRaises(InvalidTitle):check_resources('<resources/>',GOOD_FEATURE,GOOD_BASE)
        with self.assertRaises(InvalidTitle):check_resources(GOOD_BASE,GOOD_FEATURE,GOOD_BASE)
    def test_reject_wrong_title_reference(self):
        with self.assertRaises(InvalidTitle):
            check_resources(GOOD_BASE,GOOD_FEATURE.replace(TITLE,'@string/other'),None)
    def test_reject_install_time_substitution(self):
        with self.assertRaises(InvalidTitle):
            check_resources(GOOD_BASE,GOOD_FEATURE.replace('on-demand','install-time'),None)
    def test_reject_fusing_activation(self):
        with self.assertRaises(InvalidTitle):
            check_resources(GOOD_BASE,GOOD_FEATURE.replace('dist:include="false"','dist:include="true"'),None)
    def test_reject_malformed_xml_or_empty_title(self):
        with self.assertRaises(InvalidTitle):check_resources('<resources',GOOD_FEATURE,None)
        with self.assertRaises(InvalidTitle):
            check_resources(GOOD_BASE.replace('R3C06 synthetic dynamic feature',''),GOOD_FEATURE,None)

if __name__=='__main__':
    unittest.main(verbosity=2)
