#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real synthetic PNG decoder/identity and adversarial R4 P06 receipt tests."""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import struct
import tempfile
import zlib

import r4_p05_screenshot_audit as audit

SHA = '92dee5df82b874a4ca1d26a29c7a0b0694a197fa'
RUN = '43442485755'


def png(col: int, blank: bool = False) -> bytes:
    w,h=384,576
    base=(250,250,250)
    fg=((col*29)%180+35,(col*47)%160+50,(col*67)%155+45)
    b=bytearray()
    for y in range(h):
        b.append(0)
        for x in range(w):
            mark=(40 <= x < 310 and 60 <= y < 220) or (90 <= x < 190 and 240 <= y < 340)
            if mark and not blank:
                b.extend(tuple(min(255, channel + ((x // 13 + y // 17) % 24)) for channel in fg))
            else:
                b.extend(base)
    raw=zlib.compress(bytes(b),6)
    def chunk(typ,data):
        return struct.pack('>I',len(data))+typ+data+struct.pack('>I',zlib.crc32(typ+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',raw)+chunk(b'IEND',b'')


def build(root:Path):
    (root/'metadata').mkdir(parents=True)
    (root/'metadata/source-sha.txt').write_text(SHA+'\n')
    (root/'metadata/run-id.txt').write_text(RUN+'\n')
    screens=[]
    for mode in ('light','dark'):
        d=root/'screenshots'/mode
        d.mkdir(parents=True)
        for name in audit.EXPECTED:
            screens.append(d/name)
    screens.append(root/'screenshots/light/r4_real_app_launch.png')
    for i,path in enumerate(screens): path.write_bytes(png(i+1))
    (root/'logs').mkdir()
    for label,count in audit.EXPECTED_LOGS.items():
        (root/'logs'/f'{label}.txt').write_text(f'INSTRUMENTATION_CODE: -1\nOK ({count} tests)\n')
    return screens


def refused(action,code):
    try: action()
    except ValueError as e:
        assert code in str(e), (str(e),code)
    else:
        raise AssertionError('AUDIT_NEGATIVE_NOT_REFUSED: '+code)


def run():
    with tempfile.TemporaryDirectory(prefix='r4-p06-image-audit-') as t:
        root=Path(t)
        files=build(root)
        ok=audit.validate(root,SHA,RUN)
        assert ok['real_device_tests']==41
        assert len(ok['screenshots'])==23
        assert ok['screenshots_nonblank_validated']
        print('R4_P06_SYNTHETIC_41_LOG_23_SCREENSHOT_RECEIPT_PASS')
        first=files[0]
        raw=first.read_bytes()
        first.write_bytes(png(99,blank=True))
        refused(lambda:audit.validate(root,SHA,RUN),'PNG_BYTES')
        first.write_bytes(raw)
        files[2].write_bytes(files[1].read_bytes())
        refused(lambda:audit.validate(root,SHA,RUN),'IDENTICAL_SCREENSHOTS')
        files[2].write_bytes(png(3))
        files[3].write_bytes(files[3].read_bytes()[:-12])
        refused(lambda:audit.validate(root,SHA,RUN),'PNG_MISSING_COMPONENT')
        files[3].write_bytes(png(4))
        files[4].write_bytes(files[4].read_bytes()[:37]+b'Z'+files[4].read_bytes()[38:])
        refused(lambda:audit.validate(root,SHA,RUN),'PNG_CRC')
        files[4].write_bytes(png(5))
        log=root/'logs/r4-activity-dark.txt'
        log.write_text('OK (5 tests)\n')
        refused(lambda:audit.validate(root,SHA,RUN),'DEVICE_LOG')
        log.write_text('INSTRUMENTATION_CODE: -1\nOK (5 tests)\n')
        refused(lambda:audit.validate(root,'f'*40,RUN),'SOURCE_MISMATCH')
        print('R4_P06_6_MUTATION_NEGATIVES_PASS')

if __name__=='__main__':
    run()
