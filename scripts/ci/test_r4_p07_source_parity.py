#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R4 P07 Compose-tree provenance classifier offline adversarial regressions."""
import r4_p07_source_parity as m

P=m.PREFIX

def refused(fn,marker):
    try:fn()
    except m.Refused as e: assert marker in str(e),(marker,e)
    else:raise AssertionError('R4_P07_NEGATIVE_ACCEPTED_'+marker)

def main():
    x,y,z=[P+'a.kt',P+'b.kt',P+'c.kt']
    base={x:'0'*40,y:'0'*40,z:'0'*40}
    author={x:'1'*40,y:'2'*40,z:'3'*40}
    head={x:'1'*40,y:'0'*40,z:'4'*40}
    result=m.partition(base,author,head)
    assert result['exact_author']==[x]
    assert result['base_retained']==[y]
    assert result['adapted']==[z]
    m.check_classification(result,expect_author_count=3,allowed_retained={y})
    refused(lambda:m.check_classification(result,expect_author_count=2,allowed_retained={y}),
            'AUTHOR_CHANGE_INVENTORY_DRIFT')
    refused(lambda:m.check_classification(result,expect_author_count=3,allowed_retained=set()),
            'UNREVIEWED_UPSTREAM_REVERSION')
    r2=m.partition(base,author,{x:'0'*40,y:'0'*40,z:'4'*40})
    refused(lambda:m.check_classification(r2,expect_author_count=3,allowed_retained={y}),
            'UNREVIEWED_UPSTREAM_REVERSION')
    r3=m.partition(base,author,{x:'1'*40,y:'4'*40,z:'4'*40})
    m.check_classification(r3,expect_author_count=3,allowed_retained={y})
    assert r3['base_retained']==[]
    assert m.BASE_RETAINED_REVIEW and len(m.BASE_RETAINED_REVIEW)==19
    assert not set(m.BASE_RETAINED_REVIEW)&set(m.SECURITY_PATHS)
    print('R4_P07_SOURCE_PARITY_CLASSIFIER_AND_THREE_FAIL_CLOSED_NEGATIVES_PASS')

if __name__=='__main__':main()
