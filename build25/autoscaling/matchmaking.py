"""Build 25 transactional fleet allocator. One configured process = one arena.
SQLite WAL supports multiple allocator workers on ONE host. Use a single writer
or PostgreSQL transactions before distributing the control plane across hosts.
Gameplay processes can already run on separate machines. No client-supplied URLs.
"""
import json
import os
import sqlite3
import time
from contextlib import contextmanager

MODES = ('DEATHMATCH', 'TEAM DEATHMATCH', 'CAPTURE THE FLAG')
BUILD = 25

def load_fleet():
    path = os.environ.get('KNIVRA_FLEET_FILE')
    if path:
        with open(path) as f: return json.load(f)
    return json.loads(os.environ.get('KNIVRA_FLEET_JSON', '{}'))

class Matchmaker:
    def __init__(self, address='', clock=time.time, path=None, fleet=None):
        self.clock = clock
        self.fleet = fleet if fleet is not None else load_fleet()
        if not self.fleet and address:
            self.fleet = {'arena-1': {'address':address, 'capacity':7}}
        for sid, spec in self.fleet.items():
            if not isinstance(sid,str) or not isinstance(spec.get('address'),str) or not 2<=spec.get('capacity',7)<=7:
                raise ValueError('Invalid operator fleet configuration')
        self.db=sqlite3.connect(path or os.environ.get('KNIVRA_ALLOCATION_DB', ':memory:'), isolation_level=None, check_same_thread=False, timeout=10)
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS arena25 (id TEXT PRIMARY KEY, mode TEXT, desired TEXT, state TEXT, seen REAL, players TEXT);
        CREATE TABLE IF NOT EXISTS queue25 (aid TEXT PRIMARY KEY, mode TEXT, joined REAL, expires REAL);
        CREATE TABLE IF NOT EXISTS lease25 (aid TEXT PRIMARY KEY, server TEXT, mode TEXT, expires REAL, connected INTEGER DEFAULT 0);
        CREATE INDEX IF NOT EXISTS queue25_order ON queue25(mode,joined);
        CREATE INDEX IF NOT EXISTS lease25_server ON lease25(server);
        CREATE TABLE IF NOT EXISTS control25 (id TEXT PRIMARY KEY, phase TEXT, mode TEXT, changed REAL);
        CREATE TABLE IF NOT EXISTS limits25 (aid TEXT PRIMARY KEY, started REAL, count INTEGER);
        ''')

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.clean()
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def clean(self):
        now=self.clock()
        self.db.execute('DELETE FROM queue25 WHERE expires<=?',(now,))
        self.db.execute('DELETE FROM lease25 WHERE expires<=?',(now,))
        self.db.execute('DELETE FROM arena25 WHERE seen<=?',(now-12,))
        self.db.execute('DELETE FROM lease25 WHERE server NOT IN (SELECT id FROM arena25)')
        self.db.execute('DELETE FROM limits25 WHERE started<?',(now-60,))

    def allocate(self):
        for server in self.db.execute("SELECT * FROM arena25 WHERE state='lobby' AND id NOT IN (SELECT id FROM control25 WHERE phase IN ('stopping','stopped')) ORDER BY id").fetchall():
            if server['id'] not in self.fleet:continue
            players=json.loads(server['players'])
            reserved=self.db.execute('SELECT count(*) FROM lease25 WHERE server=?',(server['id'],)).fetchone()[0]
            desired=server['desired'] or server['mode']
            if not players and not reserved:
                first=self.db.execute('SELECT mode FROM queue25 ORDER BY joined,aid LIMIT 1').fetchone()
                if first:desired=first[0]
                self.db.execute('UPDATE arena25 SET desired=? WHERE id=?',(desired,server['id']))
            if server['mode']!=desired:continue
            capacity=self.fleet[server['id']].get('capacity',7)-reserved
            for item in self.db.execute('SELECT * FROM queue25 WHERE mode=? ORDER BY joined,aid LIMIT ?', (desired,max(0,capacity))).fetchall():
                self.db.execute('INSERT INTO lease25 VALUES(?,?,?,?,0)',(item['aid'],server['id'],desired,self.clock()+30))
                self.db.execute('DELETE FROM queue25 WHERE aid=?',(item['aid'],))

    def heartbeat(self,data):
        sid=data.get('server_id','arena-1');mode=data.get('mode');state=data.get('state');players=data.get('players')
        if sid not in self.fleet or data.get('build')!=BUILD or mode not in MODES or state not in ('lobby','playing','draining'):
            raise ValueError('Unsupported fleet identity, state or build.')
        if not isinstance(players,list) or len(players)>self.fleet[sid].get('capacity',7) or any(not isinstance(p,str) or len(p)!=32 for p in players) or len(set(players))!=len(players):
            raise ValueError('Invalid server roster.')
        with self.transaction():
            control=self.db.execute('SELECT phase,mode FROM control25 WHERE id=?',(sid,)).fetchone()
            if control and control['phase'] in ('stopping','stopped'): state='draining'
            old=self.db.execute('SELECT desired FROM arena25 WHERE id=?',(sid,)).fetchone()
            self.db.execute('INSERT OR REPLACE INTO arena25 VALUES(?,?,?,?,?,?)',(sid,mode,old[0] if old else (control['mode'] if control else None),state,self.clock(),json.dumps(players)))
            for aid in players:
                existing=self.db.execute('SELECT server FROM lease25 WHERE aid=?',(aid,)).fetchone()
                if existing and existing[0]!=sid:raise ValueError('Player already allocated to a different arena.')
                self.db.execute('INSERT OR REPLACE INTO lease25 VALUES(?,?,?,?,1)',(aid,sid,mode,self.clock()+60))
                self.db.execute('DELETE FROM queue25 WHERE aid=?',(aid,))
            self.allocate()
            desired=self.db.execute('SELECT desired FROM arena25 WHERE id=?',(sid,)).fetchone()[0]
            pending=self.db.execute('SELECT count(*) FROM lease25 WHERE server=? AND connected=0',(sid,)).fetchone()[0]
            return dict(ok=True,mode=desired or mode,reservations=pending,server_id=sid)

    def find(self,aid,data):
        mode=data.get('mode')
        if data.get('build')!=BUILD:raise ValueError('Update KNIVRA to Build 25 for public matchmaking.')
        if mode not in MODES:raise ValueError('Choose a public game mode.')
        with self.transaction():
            row=self.db.execute('SELECT count FROM limits25 WHERE aid=?',(aid,)).fetchone()
            if row and row[0]>=30:raise ValueError('Matchmaking rate limit; retry shortly.')
            self.db.execute('INSERT INTO limits25 VALUES(?,?,1) ON CONFLICT(aid) DO UPDATE SET count=count+1',(aid,self.clock()))
            lease=self.db.execute('SELECT * FROM lease25 WHERE aid=?',(aid,)).fetchone()
            if lease and lease['server'] not in self.fleet:
                self.db.execute('DELETE FROM lease25 WHERE aid=?',(aid,));lease=None
            if not lease:
                if self.db.execute('SELECT count(*) FROM queue25').fetchone()[0]>=10000:raise ValueError('Queue full; retry shortly.')
                old=self.db.execute('SELECT mode FROM queue25 WHERE aid=?',(aid,)).fetchone()
                if old and old[0]!=mode:self.db.execute('DELETE FROM queue25 WHERE aid=?',(aid,))
                self.db.execute('INSERT INTO queue25 VALUES(?,?,?,?) ON CONFLICT(aid) DO UPDATE SET expires=excluded.expires',(aid,mode,self.clock(),self.clock()+30))
                self.allocate()
                lease=self.db.execute('SELECT * FROM lease25 WHERE aid=?',(aid,)).fetchone()
            if lease:
                return dict(ok=True,status='ready',address=self.fleet[lease['server']]['address'],mode=lease['mode'],server_id=lease['server'],reconnect=bool(lease['connected']))
            waiting=[r[0] for r in self.db.execute('SELECT aid FROM queue25 WHERE mode=? ORDER BY joined,aid',(mode,))]
            return dict(ok=True,status='waiting',position=waiting.index(aid)+1,server_online=bool(self.db.execute('SELECT 1 FROM arena25 LIMIT 1').fetchone()))

    def cancel(self,aid):
        with self.transaction():
            self.db.execute('DELETE FROM queue25 WHERE aid=?',(aid,))
            self.db.execute('DELETE FROM lease25 WHERE aid=? AND connected=0',(aid,))
            self.allocate()
            return dict(ok=True)
