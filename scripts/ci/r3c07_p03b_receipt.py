#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C07 P03B: seal genuine API36 instrumented UI + three PNG screenshots.

Only the actual hosted runner calls this with --log/--png-*. Source-only
selftests cannot produce qualified device evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import zlib

CLASS='com.aurora.store.data.artifact.ArtifactImportJourneyP03BDeviceTest'
NAMES=('r3c07_p03b_provider_choice.png','r3c07_p03b_failed_retry.png',
       'r3c07_p03b_signed_review.png')
METHODS=('explicitProviderChoiceAndRefusalNeverAutoNavigatesOrInstalls',
    'invalidDocumentGetsSafeManualRetryAndFreshSignedReview',
    'requestedVersionMismatchBlocksRealSignedFileConsent',
    'userSourceChangeAndActivityRecreateDiscardAllOldConsent',
    'realLandscapeConfigurationAndLargeTextRetainSafeActions')
SHA=re.compile('[0-9a-f]{40}\\Z')

class Refused(RuntimeError):pass

def require(ok, reason):
    if not ok:raise Refused(reason)

def digest(b):return hashlib.sha256(b).hexdigest()

def png_info(raw):
    require(1024 <= len(raw) <= 12_000_000,'PNG absent, too small or oversized')
    require(raw[:8]==b'\x89PNG\r\n\x1a\n','not a PNG image with valid IHDR')
    offset=8
    ihdr=None
    saw_idat=False
    compressed=bytearray()
    saw_end=False
    chunks=0
    while offset < len(raw):
        require(offset+12 <= len(raw), 'truncated PNG chunk')
        length=struct.unpack('>I',raw[offset:offset+4])[0]
        kind=raw[offset+4:offset+8]
        require(length <= 12_000_000 and offset+12+length <= len(raw),
                'PNG chunk length outside file')
        payload=raw[offset+8:offset+8+length]
        crc=struct.unpack('>I',raw[offset+8+length:offset+12+length])[0]
        require(zlib.crc32(kind+payload)&0xffffffff==crc,
                'PNG chunk CRC mismatch')
        chunks+=1
        require(chunks<150, 'too many PNG chunks')
        if kind==b'IHDR':
            require(ihdr is None and offset==8 and length==13,
                    'not a PNG image with valid IHDR')
            ihdr=payload
        elif kind==b'IDAT':
            require(ihdr is not None and not saw_end, 'PNG IDAT misplaced')
            saw_idat=True
            compressed.extend(payload)
        elif kind==b'IEND':
            require(length==0 and saw_idat and offset+12==len(raw),
                    'PNG IEND absent or trailing data')
            saw_end=True
        elif kind[0]&32==0:  # Unknown *critical* chunk must be rejected.
            require(kind in {b'PLTE'},'unknown critical PNG chunk')
        offset+=12+length
        if saw_end:break
    require(ihdr is not None and saw_idat and saw_end,'incomplete PNG structure')
    w,h,depth,colour,compression,filter_method,interlace=struct.unpack('>IIBBBBB',ihdr)
    require(300<=w<=4096 and 300<=h<=4096 and depth==8 and colour in (2,6)
            and compression==0 and filter_method==0 and interlace==0,
            'unsupported/implausible screenshot PNG dimensions or encoding')
    channels=3 if colour==2 else 4
    limit=(w*channels+1)*h
    require(limit<=70_000_000, 'PNG image expansion limit exceeded')
    try:
        d=zlib.decompressobj()
        # Hard upper bound BEFORE any flush/decompress continuation. A forged
        # IDAT stream must never trigger unbounded memory expansion.
        decoded=d.decompress(bytes(compressed),limit+1)
    except zlib.error as exc:
        raise Refused('PNG deflate data invalid') from exc
    require(d.eof and not d.unused_data and not d.unconsumed_tail
            and len(decoded)==limit, 'PNG pixel stream truncated, oversized or invalid')
    row_bytes=w*channels+1
    require(all(decoded[i*row_bytes]<=4 for i in range(h)),
            'PNG row has invalid filter type')
    return {'sha256':digest(raw),'width':w,'height':h,'bytes':len(raw)}

def log_info(raw):
    require(200 <= len(raw) <= 2_000_000, 'missing/oversized instrumentation log')
    try:log=raw.decode('utf-8')
    except UnicodeError as e:raise Refused('invalid UTF8 instrumentation log') from e
    for wrong in ('FAILURES!!!','INSTRUMENTATION_FAILED','Process crashed',
                  'INSTRUMENTATION_CODE: 0','INSTRUMENTATION_STATUS_CODE: -2',
                  'INSTRUMENTATION_STATUS_CODE: -1'):
        require(wrong not in log,'instrumentation failure marker: '+wrong)
    require(CLASS in log,'wrong instrumentation class')
    require(len(re.findall(r'^OK \(5 tests\)\s*$',log,re.M))==1,
            'five real tests missing or duplicate OK banner')
    require(len(re.findall(r'^INSTRUMENTATION_CODE: -1\s*$',log,re.M))==1,
            'actual Android terminal result missing')
    require(len(re.findall(r'^INSTRUMENTATION_STATUS_CODE: 0\s*$',log,re.M))==5,
            'unexpected number of successful instrumentation test events')
    for method in METHODS:
        require('#'+method in log or re.search(r'^INSTRUMENTATION_STATUS: test='+re.escape(method)+r'\s*$',log,re.M),
                'required test method absent: '+method)
    return {'sha256':digest(raw),'actual_tests':5}

def verify(log,pngs,sha,run_id):
    require(SHA.fullmatch(sha) is not None,'source SHA absent')
    require(run_id.isdecimal() and int(run_id)>0,'GitHub run ID absent')
    require(set(pngs)==set(NAMES),'screenshot inventory mismatch')
    proof=log_info(log)
    captures={name:png_info(pngs[name]) for name in NAMES}
    require(len({p['sha256'] for p in captures.values()})==len(NAMES),
            'three screenshots cannot be duplicates')
    return {'phase':'R3C07_P03B_REAL_PROVIDER_RETRY_ROTATION',
      'overall':'PASS','source_sha':sha,'run_id':run_id,'android_api':36,
      'actual_instrumentation_tests':5,'test_class':CLASS,
      'log_sha256':proof['sha256'],'screenshots':captures,
      'real_android_content_uri_verification':True,
      'manual_provider_choice_retry_rotation_and_safe_consent_verified':True,
      'provider_listing_availability_proven':False,'publisher_authenticated':False,
      'installation_qualified':False,'real_talkback_service_qualified':False,
      'physical_device_qualified':False,'release_qualified':False}

def seal(args):
    logs=Path(args.log)
    require(logs.is_file() and not logs.is_symlink() and logs.name=='r3c07_p03b_real_ui.txt',
            'invalid as-run log identity')
    pngs={}
    for x in (args.choice,args.retry,args.review):
        p=Path(x)
        require(p.is_file() and not p.is_symlink() and p.name in NAMES,
                'invalid screenshot identity')
        require(p.name not in pngs,'duplicate screenshot name')
        pngs[p.name]=p.read_bytes()
    doc=verify(logs.read_bytes(),pngs,args.sha,args.run_id)
    path=Path(args.output)
    require(path.resolve()!=logs.resolve() and all(path.resolve()!=Path(x).resolve()
        for x in (args.choice,args.retry,args.review)), 'cannot overwrite source evidence')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(doc,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print('R3C07_P03B_REAL_API36_UI_RECEIPT_PASS sha='+args.sha+' run='+args.run_id)

def fake_png(width,height,fill):
    # Only self-test inputs: build structurally valid PNG with real CRC + IDAT.
    def chunk(kind,data):
        return (struct.pack('>I',len(data))+kind+data+
                struct.pack('>I',zlib.crc32(kind+data)&0xffffffff))
    ihdr=struct.pack('>IIBBBBB',width,height,8,2,0,0,0)
    pixel=bytes([fill,fill,fill])*width
    raw=(b'\x00'+pixel)*height
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',ihdr)+chunk(b'IDAT',zlib.compress(raw,6))+chunk(b'IEND',b'')

def corrupt_idat_with_valid_crc(raw):
    length=struct.unpack('>I',raw[33:37])[0]
    require(raw[37:41]==b'IDAT','synthetic PNG IDAT missing')
    start=41
    value=bytearray(raw)
    value[start:start+min(length,6)]=b'\x00'*min(length,6)
    value[start+length:start+length+4]=struct.pack(
        '>I',zlib.crc32(b'IDAT'+value[start:start+length])&0xffffffff)
    return bytes(value)

def selftest():
    log=('INSTRUMENTATION_STATUS: class='+CLASS+'\n'+
        ''.join('INSTRUMENTATION_STATUS: test='+m+'\nINSTRUMENTATION_STATUS_CODE: 0\n'
                for m in METHODS)+
        'OK (5 tests)\nINSTRUMENTATION_CODE: -1\n').encode()
    images={n:fake_png(1080,2160,i) for i,n in enumerate(NAMES,1)}
    good=verify(log,images,'a'*40,'42')
    require(good['overall']=='PASS','positive self-test failed')
    mutations=[('missing-method',log.replace(METHODS[0].encode(),b'replaced',1),images,'a'*40,'42'),
       ('bad-count',log.replace(b'OK (5 tests)',b'OK (4 tests)'),images,'a'*40,'42'),
       ('status-failure',log+b'FAILURES!!!\n',images,'a'*40,'42'),
       ('wrong-class',log.replace(CLASS.encode(),b'other.package.Class'),images,'a'*40,'42'),
       ('wrong-sha',log,images,'A'*40,'42'),
       ('wrong-run',log,images,'a'*40,'0'),
       ('missing-png',log,{k:v for k,v in images.items() if k!=NAMES[0]},'a'*40,'42'),
       ('duplicate-png',log,{**images,NAMES[1]:images[NAMES[0]]},'a'*40,'42'),
       ('invalid-png',log,{**images,NAMES[0]:b'x'*1030},'a'*40,'42'),
       ('truncated-png',log,{**images,NAMES[0]:images[NAMES[0]][:-12]},'a'*40,'42'),
       ('bad-crc',log,{**images,NAMES[0]:images[NAMES[0]][:43]+bytes([images[NAMES[0]][43]^1])+images[NAMES[0]][44:]},'a'*40,'42'),
       ('bad-deflate',log,{**images,NAMES[0]:corrupt_idat_with_valid_crc(images[NAMES[0]])},'a'*40,'42'),
       ('trailing-data',log,{**images,NAMES[0]:images[NAMES[0]]+b'junk'},'a'*40,'42')]
    for label,l,p,s,r in mutations:
        try:verify(l,p,s,r)
        except Refused:continue
        raise AssertionError('unsafe receipt mutation accepted: '+label)
    print('R3C07_P03B_RECEIPT_SELFTEST_PASS: 1 parser positive, '+str(len(mutations))+' negatives')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--selftest',action='store_true')
    for key in ('log','choice','retry','review','sha','run-id','output'):
        p.add_argument('--'+key,required=False)
    args=p.parse_args()
    if args.selftest:selftest();return
    require(all(getattr(args,key.replace('-','_')) for key in
        ('log','choice','retry','review','sha','run-id','output')), 'missing arguments')
    seal(args)

if __name__=='__main__':
    try:main()
    except (Refused,AssertionError,OSError,ValueError) as e:
        print('R3C07_P03B_RECEIPT_REFUSED: '+str(e),file=sys.stderr)
        raise SystemExit(2)
