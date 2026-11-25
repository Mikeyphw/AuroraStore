#!/usr/bin/env python3
"""Exercise the exact migration DDL with populated SQLite schemas; Room KSP/device gates remain separate."""
from pathlib import Path
import argparse,json,re,sqlite3,subprocess
ROOT=Path(__file__).resolve().parents[2]
DIR=ROOT/'app/schemas/com.aurora.store.data.room.AuroraDatabase'
UP=ROOT/'docs/integration/upstream-schema-16.json'
M=ROOT/'app/src/main/java/com/aurora/store/data/room/MigrationHelper.kt'

def entities(doc): return {x['tableName']:x for x in doc['database']['entities']}
def sql_from_source():
    text=M.read_text();old=text.split('val MIGRATION_15_16 =',1)[1].split('val MIGRATION_16_17 =',1)[0];new=text.split('val MIGRATION_16_17 =',1)[1].split('private const val TAG',1)[0]
    create=''.join(re.findall(r'^\s*"([^"\n]*)"\s*\+?\s*$',old,re.M))
    assert create.startswith('CREATE TABLE IF NOT EXISTS `play_delivery_evidence`')
    assert 'MIGRATION_15_16.migrate(db)' in new
    drops=re.findall(r'db.execSQL\("([^"]+)"\)',new)
    assert drops==['DROP TABLE IF EXISTS `exodus_tracker`'],drops
    return create,drops[0]

def create(conn,doc):
    for t in entities(doc).values():
        conn.execute(t['createSql'].replace('${TABLE_NAME}',t['tableName']))
        for idx in t.get('indices',[]): conn.execute(idx['createSql'].replace('${TABLE_NAME}',t['tableName']))
    for q in doc['database']['setupQueries']:conn.execute(q)

def schema_sql(doc):
    c=sqlite3.connect(':memory:');create(c,doc);result=shape(c);c.close();return result

def shape(c):
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'") if r[0]!='room_master_table'}
    return {t:(c.execute(f'PRAGMA table_info(`{t}`)').fetchall(),c.execute(f'PRAGMA foreign_key_list(`{t}`)').fetchall(),c.execute(f'PRAGMA index_list(`{t}`)').fetchall()) for t in tables}

def verify(generated=None):
    v15=json.loads((DIR/'15.json').read_text());fork=json.loads((DIR/'16.json').read_text());up=json.loads(UP.read_text())
    assert fork['database']['identityHash']=='daa8dbc1dc7b57377b22b569846b7c85'
    assert up['database']['identityHash']=='f65ba0d37b1f92e464f095e617ff09e1'
    expected=entities(fork);del expected['exodus_tracker']
    expected_doc={'database':{'entities':list(expected.values()),'setupQueries':[]}}
    target=ROOT/'app/src/main/java/com/aurora/store/data/room/AuroraDatabase.kt'
    assert 'version = 17' in target.read_text() and 'TrackerEntity::class' not in target.read_text()
    create_sql,drop_sql=sql_from_source()
    for label,doc in [('v15',v15),('fork-v16',fork),('upstream-v16',up)]:
        c=sqlite3.connect(':memory:');c.execute('PRAGMA foreign_keys=ON');create(c,doc)
        c.execute("INSERT INTO account (id,type,email,tokenType,authViaMicroG,isDefault,addedAt) VALUES ('fixture','ANONYMOUS','','NONE',0,1,1234)")
        c.execute("INSERT INTO app_account_binding VALUES ('fixture.pkg','fixture')")
        c.execute("INSERT INTO download VALUES ('fixture.pkg',737,0,0,'preserve','',8,0,'FAILED',0,0,0,1,0,'[]','[]',23,9001,0)")
        if label=='fork-v16':c.execute("INSERT INTO play_delivery_evidence VALUES ('fixture.pkg',737,9001,'opaque','fixture','URLS_RESOLVED_NOT_VERIFIED',NULL,NULL,2)")
        before={t:c.execute(f'SELECT * FROM `{t}`').fetchall() for t in entities(doc) if t!='exodus_tracker'}
        # Both production migration paths call the same idempotent CREATE; neither touches persisted evidence.
        if label=='v15':c.execute(create_sql)
        c.execute(create_sql);c.execute(drop_sql)
        for t,rows in before.items(): assert c.execute(f'SELECT * FROM `{t}`').fetchall()==rows,(label,t)
        assert shape(c)==schema_sql(expected_doc),(label,'schema shape')
        assert c.execute('PRAGMA integrity_check').fetchone()==('ok',)
        assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert c.execute('SELECT count(*) FROM play_delivery_evidence').fetchone()[0]==int(label=='fork-v16')
        c.close();print('AUR_INT01_SQLITE_MIGRATION_PASS',label)
    if generated:
        doc=json.loads(Path(generated).read_text());assert doc['database']['version']==17
        assert entities(doc)==expected,'HOSTED_ROOM_V17_ENTITY_DRIFT'
        assert re.fullmatch('[a-f0-9]{32}',doc['database']['identityHash'])
        assert doc['database']['identityHash'] not in (v15['database']['identityHash'],fork['database']['identityHash'],up['database']['identityHash'])
        print('AUR_INT01_HOSTED_SCHEMA17_ENTITIES_PASS')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--generated');verify(p.parse_args().generated)
