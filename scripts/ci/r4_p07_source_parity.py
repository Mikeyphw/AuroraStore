#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline, Git-tree-authenticated PR113/R3D Compose source parity inventory.

This is an *inventory*, not evidence that an adapted UI matches the author's
pixels/behavior. It rejects an unreviewed return to pre-port R3D Compose sources.
No network, Gradle, downloads or Android device operations.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

REPO = 'Mikeyphw/AuroraStore'
BASE = '4afa0a40815da035547d7b62460d56bc6d0e26bc'
AUTHOR = '8ff1cbc8d252cee26507372b8ead59d72872c9da'
MERGE = '340ecef9ffd8235a6e721ca37604fc380728fbf4'
PREFIX = 'app/src/main/java/com/aurora/store/compose/'
BASE_RETAINED_REVIEW = frozenset({
    'app/src/main/java/com/aurora/store/compose/composable/DownloadListItem.kt',
    'app/src/main/java/com/aurora/store/compose/composable/PermissionList.kt',
    'app/src/main/java/com/aurora/store/compose/preview/AppPreviewProvider.kt',
    'app/src/main/java/com/aurora/store/compose/preview/ReviewPreviewProvider.kt',
    'app/src/main/java/com/aurora/store/compose/ui/accounts/GoogleLoginScreen.kt',
    'app/src/main/java/com/aurora/store/compose/ui/commons/CategoryBrowseScreen.kt',
    'app/src/main/java/com/aurora/store/compose/ui/commons/PermissionRationaleScreen.kt',
    'app/src/main/java/com/aurora/store/compose/ui/commons/SortFilter.kt',
    'app/src/main/java/com/aurora/store/compose/ui/details/ScreenshotScreen.kt',
    'app/src/main/java/com/aurora/store/compose/ui/details/composable/DeveloperDetails.kt',
    'app/src/main/java/com/aurora/store/compose/ui/downloads/DownloadsScreen.kt',
    'app/src/main/java/com/aurora/store/compose/ui/favourite/FavouriteScreen.kt',
    'app/src/main/java/com/aurora/store/compose/ui/installed/InstalledScreen.kt',
    'app/src/main/java/com/aurora/store/compose/ui/notifications/NotificationsScreen.kt',
    'app/src/main/java/com/aurora/store/compose/ui/preferences/installation/InstallerScreen.kt',
    'app/src/main/java/com/aurora/store/compose/ui/sheets/DownloadActionsSheet.kt',
    'app/src/main/java/com/aurora/store/compose/ui/sheets/VersionPickerSheet.kt',
    'app/src/main/java/com/aurora/store/compose/ui/splash/SplashScreen.kt',
    'app/src/main/java/com/aurora/store/compose/ui/spoof/SpoofScreen.kt',
})
SECURITY_PATHS = (
    'scripts/ci/r3c07_hf03_apk_pair.py',
    'scripts/ci/test_r3c07_hf03_optimization.py',
)

class Refused(RuntimeError): pass

def need(test, reason):
    if not test: raise Refused('R4_P07_PARITY_REFUSED_'+reason)

def git(repo:Path, *args:str) -> str:
    proc=subprocess.run(['git',*args],cwd=repo,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    need(proc.returncode==0,'GIT_COMMAND_FAILED_'+str(args)+'_'+proc.stderr.decode('utf-8','replace')[-200:])
    return proc.stdout.decode().strip()

def tree(repo:Path, sha:str) -> dict[str,str]:
    proc=subprocess.run(['git','ls-tree','-r','-z',sha],cwd=repo,capture_output=True)
    need(proc.returncode==0,'MISSING_GIT_TREE_'+sha)
    result={}
    for record in proc.stdout.split(b'\0'):
        if not record: continue
        meta, sep, path = record.partition(b'\t')
        need(bool(sep),'INVALID_GIT_TREE_RECORD')
        parts=meta.decode().split()
        need(len(parts)==3,'INVALID_GIT_TREE_META')
        if parts[1] == 'blob':result[path.decode()]=parts[2]
    return result

def partition(base:dict[str,str],author:dict[str,str],head:dict[str,str]):
    paths=sorted(p for p,v in author.items() if p.startswith(PREFIX) and base.get(p)!=v)
    exactly=[];retained=[];adapted=[]
    for path in paths:
        actual=head.get(path)
        if actual==author[path]: exactly.append(path)
        elif actual==base.get(path): retained.append(path)
        else: adapted.append(path)
    return dict(author_changed=paths,exact_author=exactly,base_retained=retained,adapted=adapted)

def check_classification(result:dict, *, expect_author_count=100,
                         allowed_retained=BASE_RETAINED_REVIEW):
    need(len(result['author_changed'])==expect_author_count,'AUTHOR_CHANGE_INVENTORY_DRIFT')
    unexpected=set(result['base_retained'])-set(allowed_retained)
    need(not unexpected,'UNREVIEWED_UPSTREAM_REVERSION_'+','.join(sorted(unexpected)))
    need(len(result['exact_author'])+len(result['base_retained'])+
         len(result['adapted'])==len(result['author_changed']),'CLASSIFICATION_LOST_PATH')
    # A later reviewed adaptation may intentionally reduce this backlog.
    need(len(result['base_retained'])<=len(allowed_retained),'BACKLOG_INCREASED')

def review(repo:Path, at: str = 'HEAD') -> dict:
    # P08 may audit the exact historical P11 tree instead of inheriting post-P11 UI edits.
    head=git(repo,'rev-parse',at)
    need(re.fullmatch('[a-f0-9]{40}',head) is not None,'HEAD_NOT_SHA')
    need(git(repo,'rev-list','--parents','-n','1',MERGE).split()==[MERGE,BASE,AUTHOR],
         'PR113_MERGE_PARENTS_CHANGED')
    need(subprocess.run(['git','merge-base','--is-ancestor',MERGE,head],cwd=repo).returncode==0,
         'PR113_MERGE_NOT_ANCESTOR')
    for path in SECURITY_PATHS:
        need(git(repo,'rev-parse',head+':'+path)==git(repo,'rev-parse',BASE+':'+path),
             'R3D_SECURITY_PATH_CHANGED_'+path)
    result=partition(tree(repo,BASE),tree(repo,AUTHOR),tree(repo,head))
    check_classification(result)
    counts={k:len(v) for k,v in result.items()}
    return {
        'schema':1,'kind':'aurora-r4-pr113-r3d-compose-parity-inventory',
        'source_sha':head,'r3d_base_sha':BASE,'pr113_author_sha':AUTHOR,
        'genuine_merge_sha':MERGE,'counts':counts,
        'classification':result,
        'upstream_ui_byte_identity_is_not_visual_parity':True,
        'base_retained_requires_manual_file_review':True,
        'manual_visual_approved':False,
        'offline_fixture_scope_only':True,
        'physical_arm64_qualified':False,
        'live_google_play_qualified':False,
        'release_qualified':False,
    }

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path('.'))
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    result=review(args.repo.resolve(strict=True))
    if args.out:
        need(not args.out.exists(),'OUTPUT_ALREADY_EXISTS')
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('R4_P07_SOURCE_PARITY_100_AUTHOR_UI_PATHS_CLASSIFIED_PASS '+json.dumps(result['counts'],sort_keys=True))
    print('R4_P07_19_OR_FEWER_R3D_BASE_RETAINED_REQUIRE_MANUAL_REVIEW')

if __name__=='__main__':
    try:main()
    except (Refused,OSError,ValueError) as exc:
        print(str(exc),file=sys.stderr);raise SystemExit(2)
