#!/usr/bin/env python3
"""R3B HF09 — reproducible, source-pinned wrapping fix (default: --check)."""
# SPDX-License-Identifier: GPL-3.0-or-later
from argparse import ArgumentParser
from pathlib import Path
from hashlib import sha1
import os
import subprocess

BASE = '1f4e751432794a21f007b04a0c94a31e4e726ab2'
TREE = '67f7ece4089d2a8cd12c0d32a1915d23325f1abe'
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'app/src/main/java/com/aurora/store'
EDITS = {'data/installer/verification/ApkSetVerifier.kt': [('if (!packagePattern.matches(lib.packageName) || lib.versionCode <= 0L ||', 'if (!packagePattern.matches(lib.packageName) ||\n                    lib.versionCode <= 0L ||'), ('if (entry.name.isEmpty() || !entry.name.endsWith(".apk") ||', 'if (entry.name.isEmpty() ||\n                    !entry.name.endsWith(".apk") ||'), ('entry.name == ".apk" || File(entry.name).name != entry.name ||', 'entry.name == ".apk" ||\n                    File(entry.name).name != entry.name ||'), (' || entry.name.contains("..") ||', ' ||\n                    entry.name.contains("..") ||'), ('if (!path.isFile || path.length() != entry.metadata.size ||', 'if (!path.isFile ||\n                path.length() != entry.metadata.size ||'), ('if (signed.isEmpty() || (', 'if (signed.isEmpty() ||\n                    ('), ('info != null && signingDigests(info).let {', 'info != null &&\n                            signingDigests(info).let {')], 'data/installer/verification/BinaryApkManifest.kt': [('if (count < 0 || count > 50000 || stringsStart < header ||', 'if (count < 0 ||\n            count > 50000 ||\n            stringsStart < header ||'), ('if (buf.limit() < 8 || ushort(buf, offset) != type ||', 'if (buf.limit() < 8 ||\n            ushort(buf, offset) != type ||')], 'data/room/download/Download.kt': [('apk.name.endsWith(".apk") && File(apk.name).name == apk.name &&', 'apk.name.endsWith(".apk") &&\n                File(apk.name).name == apk.name &&'), ('apk.size > 0L && PathUtil.getLocalFile(context, apk, this).let { file ->', 'apk.size > 0L &&\n                PathUtil.getLocalFile(context, apk, this).let { file ->'), ('file.isFile && file.length() == apk.size &&', 'file.isFile &&\n                        file.length() == apk.size &&')]}
BLOBS = {'data/installer/verification/ApkSetVerifier.kt': '91d466b431c8542da0f9f8bef7b4d9c89be20ffb', 'data/installer/verification/BinaryApkManifest.kt': 'dc51bf893a0856e9ddc56f21b376e81b8f860e13', 'data/room/download/Download.kt': '556f2a6165465e49e9714168d5709664f6531140'}

def blob(data):
    return sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()

def check():
    for rel, pairs in EDITS.items():
        path = SRC / rel
        if path.is_symlink() or not path.is_file():
            raise SystemExit('HF09_PATCH_REFUSED: missing/symlink ' + rel)
        data = path.read_text()
        for before, after in pairs:
            if before in data or data.count(after) != 1:
                raise SystemExit('HF09_PATCH_REFUSED: wrapping regression ' + rel)
    print('R3B_HF09_CONDITION_PATCH_CHECK_PASS')

def apply():
    def git(*args):
        p = subprocess.run(['git','-C',str(ROOT),*args], capture_output=True,text=True,check=True)
        return p.stdout.strip()
    if git('branch','--show-current')!='master' or git('rev-parse','HEAD')!=BASE:
        raise SystemExit('HF09_PATCH_REFUSED: wrong branch or base')
    if git('rev-parse','HEAD^{tree}')!=TREE or git('status','--porcelain'):
        raise SystemExit('HF09_PATCH_REFUSED: wrong tree or dirty worktree')
    changes = {}
    for rel,pairs in EDITS.items():
        path=SRC/rel
        if path.is_symlink() or not path.is_file() or blob(path.read_bytes()) != BLOBS[rel]:
            raise SystemExit('HF09_PATCH_REFUSED: source blob mismatch ' + rel)
        raw=path.read_text(); fixed=raw
        for before,after in pairs:
            if fixed.count(before) != 1:
                raise SystemExit('HF09_PATCH_REFUSED: expected exactly one match ' + rel)
            fixed=fixed.replace(before,after,1)
        if ''.join(raw.split())!=''.join(fixed.split()):
            raise SystemExit('HF09_PATCH_REFUSED: executable content changed ' + rel)
        changes[path]=fixed
    for path,fixed in changes.items():
        path.write_text(fixed)
    check()
    print('R3B_HF09_CONDITION_PATCH_APPLY_PASS: changes uncommitted')

if __name__ == '__main__':
    parser=ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Apply on exact pre-HF09 clean master')
    args=parser.parse_args()
    apply() if args.apply else check()
