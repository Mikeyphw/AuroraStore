#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic negative tests only; never claim real APK signing without Android tools."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock
import r4_p06_apk_reuse as m

SHA='78340ef424cd6845241b24dd0c79dc2e5de70065'
ENV={'GITHUB_SHA':SHA,'GITHUB_REPOSITORY':m.REPO,
     'GITHUB_REF':'refs/heads/'+m.BRANCH,'GITHUB_EVENT_NAME':'push','GH_TOKEN':'test-only'}


def fail(fn,marker):
    try:fn()
    except m.Refused as e:
        assert marker in str(e),(marker,str(e))
    else:raise AssertionError('ACCEPTED_NEGATIVE '+marker)

class Pair:
    MANIFEST='manifest.json'
    NAMES={'app':'app.apk','androidTest':'androidTest.apk'}
    ROLE_PATHS={'app':Path('app/build/outputs/apk/vanilla/debug'),
                'androidTest':Path('app/build/outputs/apk/androidTest')}
    def __init__(self,run=True,artifact=True,bad_file=False,bad_signer=False):
        self.run=run;self.artifact=artifact;self.bad_file=bad_file;self.bad_signer=bad_signer
        self.selected=0
    def exact_head(self,root,sha):return sha
    def selected_run(self,sha):
        self.selected+=1
        return {'id':100,'run_attempt':1} if self.run else None
    def matching_artifact(self,run,sha):return {'id':5} if self.artifact else None
    def download_artifact(self,artifact,run):
        doc={'files':{'app':{'size':2},'androidTest':{'size':2}}}
        out={'app.apk':b'PK','androidTest.apk':b'PK',self.MANIFEST:json.dumps(doc).encode()}
        if self.bad_file:out['extra.dll']=b'anything'
        return out
    def verify_doc(self,*args):return None
    def validate_pair(self,*args):
        return {'app':{'size':200 if self.bad_signer else 2},'androidTest':{'size':2}}
    @staticmethod
    def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    negatives=0
    for key,value,marker in [
        ('GITHUB_SHA','0'*40,'GITHUB_SHA_DRIFT'),
        ('GITHUB_REPOSITORY','NotAurora/Repo','WRONG_REPOSITORY'),
        ('GITHUB_REF','refs/heads/master','WRONG_BRANCH'),
        ('GITHUB_EVENT_NAME','pull_request','WRONG_EVENT'),
        ('GH_TOKEN','','TOKEN_REQUIRED'),
    ]:
        env={**ENV,key:value}
        fail(lambda:m.validate_context(SHA,env),marker);negatives+=1
    fail(lambda:m.validate_context('xyz',ENV),'INVALID_SHA');negatives+=1
    with tempfile.TemporaryDirectory(prefix='r4-hf17-test-') as d:
        root=Path(d)/'repo';root.mkdir()
        out=Path(d)/'gh_output.txt';tmp=Path(d)/'verified'
        p=Pair(run=False)
        assert m.probe(root,SHA,tmp,out,0,p,lambda n:None,ENV) is False
        assert out.read_text()=='reused=false\n' and not tmp.exists()
        print('R4_P06_HF17_NO_TARGETED_RUN_NO_UNVERIFIED_APK_REUSE_PASS')
        out.unlink()
        p=Pair(run=True,artifact=False)
        assert m.probe(root,SHA,tmp,out,0,p,lambda n:None,ENV) is False
        assert out.read_text()=='reused=false\n' and not tmp.exists()
        out.unlink()
        p=Pair(bad_file=True)
        fail(lambda:m.probe(root,SHA,tmp,out,0,p,lambda n:None,ENV),'ARTIFACT_FILE_SET_DRIFT');negatives+=1
        assert not tmp.exists() and not out.exists()
        p=Pair(bad_signer=True)
        fail(lambda:m.probe(root,SHA,tmp,out,0,p,lambda n:None,ENV),'APK_SIGNER_OR_DIGEST_DRIFT');negatives+=1
        assert not tmp.exists() and not out.exists()
        p=Pair()
        assert m.probe(root,SHA,tmp,out,0,p,lambda n:None,ENV) is True
        assert out.read_text()=='reused=true\n'
        assert (root/p.ROLE_PATHS['app']/'app.apk').read_bytes()==b'PK'
        assert (tmp/'reuse-source.json').is_file()
        print('R4_P06_HF17_SYNTHETIC_SUCCESSFUL_PROVENANCE_BOUND_APK_COPY_PASS')
        fail(lambda:m.probe(root,SHA,tmp,out,0,p,lambda n:None,ENV),'TEMP_OUTPUT_EXISTS');negatives+=1
    assert negatives==9,negatives
    print('R4_P06_HF17_NINE_MUTATION_AND_PROVENANCE_NEGATIVES_PASS')

if __name__=='__main__':main()
