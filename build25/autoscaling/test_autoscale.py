import tempfile,unittest
from matchmaking import Matchmaker,MODES
from autoscale import Supervisor

class ScalingTest(unittest.TestCase):
 def setUp(self):
  self.now=1000.;self.tmp=tempfile.TemporaryDirectory();self.fleet={f'arena-{i}':dict(address=f'127.0.0.1:{27843+i}',capacity=7) for i in range(1,5)}
  self.m=Matchmaker(path=self.tmp.name+'/db',fleet=self.fleet,clock=lambda:self.now)
  self.started=[];self.stopped=[]
  def start(sid,mode):self.started.append((sid,mode));return {'sid':sid,'alive':True}
  self.s=Supervisor(self.m,start,lambda job:self.stopped.append(job['sid']),lambda j:j['alive'],list(self.fleet)[1:],clock=lambda:self.now)
  self.beat('arena-1')
 def tearDown(self):self.m.db.close();self.tmp.cleanup()
 def beat(self,sid,players=None,state='lobby',mode=MODES[0]):return self.m.heartbeat(dict(server_id=sid,mode=mode,state=state,players=players or [],build=25))
 def find(self,i,mode=MODES[0]):return self.m.find(f'{i:032x}',dict(mode=mode,build=25))
 def fill(self,n=8):
  for i in range(n):self.find(i)
 def test_full_starts_and_waits_for_readiness(self):
  self.fill();self.s.tick();self.assertEqual(self.started,[('arena-2',MODES[0])]);self.assertEqual(self.find(7)['status'],'waiting')
  for _ in range(5):self.s.tick()
  self.assertEqual(len(self.started),1)
  self.beat('arena-2');r=self.find(7);self.assertEqual(r['server_id'],'arena-2')
 def test_host_limit_and_overflow(self):
  self.fill(40);self.s.tick();self.assertEqual(len(self.started),3)
  for sid in self.s.jobs:self.beat(sid)
  self.s.tick();self.assertEqual(self.m.db.execute('SELECT count(*) FROM lease25').fetchone()[0],28)
  self.assertEqual(self.find(39)['status'],'waiting');self.assertEqual(len(self.started),3)
 def test_idle_retires_and_late_heartbeat_cannot_reopen(self):
  self.fill();self.s.tick();self.beat('arena-2');self.s.tick()
  for i in range(8):self.m.cancel(f'{i:032x}')
  self.s.tick()
  self.now+=121;self.beat('arena-1');self.beat('arena-2');self.s.tick()
  self.assertEqual(self.stopped,['arena-2']);self.assertNotIn('arena-1',self.stopped)
  self.beat('arena-2');self.assertEqual(self.m.db.execute("SELECT state FROM arena25 WHERE id='arena-2'").fetchone()[0],'draining')
 def test_reservations_and_players_prevent_shutdown(self):
  self.fill();self.s.tick();self.beat('arena-2');self.s.tick();aid=f'{7:032x}'
  self.now+=130;self.beat('arena-2',[aid],'playing');self.s.tick();self.assertFalse(self.stopped)
  self.now+=3;self.beat('arena-2',[],'playing');self.s.tick();self.assertFalse(self.stopped)
  self.assertTrue(self.find(7)['reconnect'])
 def test_stale_heartbeat_never_means_empty(self):
  self.fill();self.s.tick();self.beat('arena-2');self.s.tick();self.now+=200;self.s.tick();self.assertFalse(self.stopped)
 def test_start_failure_and_cooldown(self):
  self.fill();self.s.start=lambda *args:(_ for _ in ()).throw(OSError('test spawn failure'));self.s.tick()
  self.assertFalse(self.s.jobs);self.assertGreater(self.s.retry['arena-2'],self.now)
 def test_failed_boot_reclaimed(self):
  self.fill();self.s.tick();self.now+=61;self.s.tick();self.assertEqual(self.stopped,['arena-2'])
 def test_crash_detected_and_cooldown(self):
  self.fill();self.s.tick();self.s.jobs['arena-2']['alive']=False;self.s.tick();self.assertNotIn('arena-2',self.s.jobs)
 def test_modes_and_transition_dont_overlaunch(self):
  self.fill(7);self.find(7,MODES[1]);self.s.tick();self.assertEqual(self.started,[('arena-2',MODES[1])])
  self.beat('arena-2',mode=MODES[0]);self.s.tick();self.assertEqual(len(self.started),1)
  self.beat('arena-2',mode=MODES[1]);self.assertEqual(self.find(7,MODES[1])['server_id'],'arena-2')
 def test_shutdown_drains_without_kicking(self):
  self.fill();self.s.tick();self.beat('arena-2',[f'{7:032x}'],'playing');self.s.closing=True;self.s.tick()
  self.assertFalse(self.stopped);self.assertEqual(self.m.db.execute("SELECT phase FROM control25 WHERE id='arena-2'").fetchone()[0],'stopping')

 def test_allocation_is_fenced_before_stop_callback(self):
  self.fill();self.s.tick();self.beat('arena-2');self.s.tick()
  for i in range(8):self.m.cancel(f'{i:032x}')
  self.s.tick();self.now+=121;self.beat('arena-1');self.beat('arena-2')
  def stop(job):
   self.beat('arena-2')
   self.assertEqual(self.m.db.execute("SELECT state FROM arena25 WHERE id='arena-2'").fetchone()[0],'draining')
   for i in range(8):r=self.find(100+i)
   self.assertEqual(r['status'],'waiting')
  self.s.stop=stop;self.s.tick()

if __name__=='__main__':unittest.main()
