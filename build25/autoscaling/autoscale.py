#!/usr/bin/env python3
"""Demand-driven, bounded local arena supervisor. Never allocates until heartbeat ready."""
import fcntl,json,logging,os,signal,subprocess,time
from pathlib import Path
from matchmaking import Matchmaker,MODES

class Supervisor:
    def __init__(self, matchmaker, start, stop, alive, managed, idle_seconds=120, boot_seconds=60, clock=time.time):
        self.m=matchmaker; self.start=start; self.stop=stop; self.alive=alive
        self.managed=tuple(managed); self.idle_seconds=idle_seconds; self.boot_seconds=boot_seconds; self.clock=clock
        self.jobs={}; self.idle={}; self.retry={}; self.closing=False

    def tick(self):
        now=self.clock(); starts=[]; stops=[]
        # Process status is inspected outside the database transaction.
        dead={sid for sid,job in self.jobs.items() if not self.alive(job)}
        with self.m.transaction():
            for sid in dead:
                self.m.db.execute('DELETE FROM arena25 WHERE id=?',(sid,))
                self.m.db.execute('DELETE FROM lease25 WHERE server=?',(sid,))
                self.m.db.execute("UPDATE control25 SET phase='stopped',changed=? WHERE id=?",(now,sid))
                self.jobs.pop(sid);self.idle.pop(sid,None);self.retry[sid]=now+60
                logging.warning('Arena %s exited; retry cooldown started',sid)
            self.m.allocate()
            rows={r['id']:r for r in self.m.db.execute('SELECT * FROM arena25')}
            controls={r['id']:r for r in self.m.db.execute('SELECT * FROM control25')}
            queued={r['mode']:r['n'] for r in self.m.db.execute('SELECT mode,count(*) n FROM queue25 GROUP BY mode')}
            boot_capacity={mode:0 for mode in MODES}
            for sid in self.jobs:
                c=controls.get(sid);row=rows.get(sid)
                if self.closing:
                    self.m.db.execute("UPDATE control25 SET phase='stopping' WHERE id=?",(sid,))
                    self.m.db.execute("UPDATE arena25 SET state='draining' WHERE id=?",(sid,))
                if c and c['phase']=='starting' and not self.closing:
                    if row and row['seen']>=c['changed']:
                        self.m.db.execute("UPDATE control25 SET phase='running' WHERE id=?",(sid,))
                    elif now-c['changed']<self.boot_seconds:
                        boot_capacity[c['mode']]+=self.m.fleet[sid].get('capacity',7);continue
                    else:
                        # Never-ready child has never accepted allocator traffic.
                        self.m.db.execute("UPDATE control25 SET phase='stopping',changed=? WHERE id=?",(now,sid));stops.append(sid);continue
                if row and row['state']=='lobby' and row['desired'] and row['mode']!=row['desired']:
                    boot_capacity[row['desired']]+=self.m.fleet[sid].get('capacity',7)
                if not row or row['seen']<now-12:
                    # Unknown/stale is not evidence of an empty live game.
                    self.idle.pop(sid,None);continue
                leases=self.m.db.execute('SELECT count(*) FROM lease25 WHERE server=?',(sid,)).fetchone()[0]
                if json.loads(row['players']) or leases:
                    self.idle.pop(sid,None);continue
                self.idle.setdefault(sid,now)
                demand=any(queued.values())
                if self.closing or (not demand and now-self.idle[sid]>=self.idle_seconds):
                    # This transaction fences allocation and heartbeats BEFORE termination.
                    self.m.db.execute("UPDATE control25 SET phase='stopping',changed=? WHERE id=?",(now,sid))
                    self.m.db.execute("UPDATE arena25 SET state='draining' WHERE id=?",(sid,));stops.append(sid)
            if not self.closing:
                available=[s for s in self.managed if s not in self.jobs and self.retry.get(s,0)<=now]
                # Oldest waiting mode first; no speculative empty servers or duplicate boots.
                modes=[r[0] for r in self.m.db.execute('SELECT mode FROM queue25 GROUP BY mode ORDER BY min(joined)')]
                for mode in modes:
                    need=max(0,queued[mode]-boot_capacity[mode])
                    while need and available:
                        sid=available.pop(0);starts.append((sid,mode));need=max(0,need-self.m.fleet[sid].get('capacity',7))
                        self.m.db.execute('DELETE FROM arena25 WHERE id=?',(sid,))
                        self.m.db.execute('INSERT OR REPLACE INTO control25 VALUES(?,?,?,?)',(sid,'starting',mode,now))
        for sid in stops:
            # Blocking process termination never holds the allocation database lock.
            self.stop(self.jobs[sid]); self.jobs.pop(sid); self.idle.pop(sid,None); self.retry[sid]=now+60
            with self.m.transaction():
                self.m.db.execute('DELETE FROM arena25 WHERE id=?',(sid,))
                self.m.db.execute("UPDATE control25 SET phase='stopped',changed=? WHERE id=?",(now,sid))
            logging.info('Stopped empty or never-ready arena %s',sid)
        for sid,mode in starts:
            try:self.jobs[sid]=self.start(sid,mode);logging.info('Starting %s for %s',sid,mode)
            except Exception:
                self.retry[sid]=now+60
                with self.m.transaction():self.m.db.execute("UPDATE control25 SET phase='stopped',changed=? WHERE id=?",(now,sid))
                logging.exception('Arena launch failed: %s',sid)


def main():
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    root=Path(os.environ.get('KNIVRA_AUTOSCALE_STATE','/var/lib/knivra-autoscale'));root.mkdir(parents=True,exist_ok=True)
    lock=(root/'supervisor.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    m=Matchmaker();managed=[sid for sid,spec in m.fleet.items() if spec.get('managed',False)]
    if not managed:raise RuntimeError('No managed arenas configured')
    def start(sid,mode):
        spec=m.fleet[sid];port=spec['port']
        if not isinstance(port,int) or not 1024<=port<=65535:raise ValueError('Invalid operator arena port')
        state=root/sid;state.mkdir(exist_ok=True)
        env=dict(os.environ,KNIVRA_SERVER_ID=sid,KNIVRA_GAME_PORT=str(port),XDG_DATA_HOME=str(state),XDG_CONFIG_HOME=str(state))
        # Launcher reads systemd credentials; no credentials in args, source or logs.
        return subprocess.Popen(['/usr/bin/python3','/opt/knivra-public/run-public.py'],env=env)
    def stop(job):
        job.terminate()
        try:job.wait(timeout=10)
        except subprocess.TimeoutExpired:job.kill();job.wait(timeout=5)
    sup=Supervisor(m,start,stop,lambda p:p.poll() is None,managed,
        idle_seconds=max(30,int(os.environ.get('KNIVRA_IDLE_SECONDS','120'))))
    signal.signal(signal.SIGTERM,lambda *_:setattr(sup,'closing',True))
    signal.signal(signal.SIGINT,lambda *_:setattr(sup,'closing',True))
    while True:
        try:sup.tick()
        except Exception:logging.exception('Supervisor tick failed; preserving running arenas')
        if sup.closing and not sup.jobs:break
        time.sleep(2)
    m.db.close()

if __name__=='__main__':main()
