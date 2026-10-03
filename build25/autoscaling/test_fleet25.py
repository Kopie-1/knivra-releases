import tempfile,time,unittest,concurrent.futures,os,json
from matchmaking import Matchmaker,MODES

class FleetTest(unittest.TestCase):
 def setUp(self):
  self.t=1000.;self.tmp=tempfile.TemporaryDirectory();self.path=self.tmp.name+'/fleet.db'
  self.fleet={f'arena-{i}':dict(address=f'127.0.0.1:{28000+i}',capacity=7) for i in range(4)}
  self.m=Matchmaker(clock=lambda:self.t,path=self.path,fleet=self.fleet)
  for sid in self.fleet:self.beat(sid)
 def tearDown(self):self.m.db.close();self.tmp.cleanup()
 def beat(self,sid,players=None,state='lobby'):
  return self.m.heartbeat(dict(server_id=sid,mode=MODES[0],state=state,players=players or [],build=25))
 def test_capacity_and_queue(self):
  responses=[self.m.find(f'{i:032x}',dict(mode=MODES[0],build=25)) for i in range(40)]
  self.assertEqual(sum(r['status']=='ready' for r in responses),28)
  self.assertEqual(self.m.db.execute('SELECT max(n) FROM (SELECT count(*) n FROM lease25 GROUP BY server)').fetchone()[0],7)
 def test_stale_and_reconnect(self):
  aid='a'*32;r=self.m.find(aid,dict(mode=MODES[0],build=25));sid=r['server_id']
  self.beat(sid,[aid],'playing');self.beat(sid,[],'playing')
  r2=self.m.find(aid,dict(mode=MODES[0],build=25));self.assertTrue(r2['reconnect']);self.assertEqual(r['address'],r2['address'])
  self.t+=13;r3=self.m.find(aid,dict(mode=MODES[0],build=25));self.assertEqual(r3['status'],'waiting')
 def test_reject_unconfigured_and_old(self):
  with self.assertRaises(ValueError):self.beat('hostile-address')
  with self.assertRaises(ValueError):self.m.find('b'*32,dict(mode=MODES[0],build=24))
 def test_rate_limit(self):
  for i in range(30):self.m.find('c'*32,dict(mode=MODES[0],build=25))
  with self.assertRaises(ValueError):self.m.find('c'*32,dict(mode=MODES[0],build=25))
 def test_concurrent_workers(self):
  def client(i):
   m=Matchmaker(clock=lambda:1000.,path=self.path,fleet=self.fleet)
   try:return m.find(f'{i:032x}',dict(mode=MODES[0],build=25))
   finally:m.db.close()
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:responses=list(pool.map(client,range(100)))
  self.assertEqual(sum(r['status']=='ready' for r in responses),28)
 def test_restart_preserves_leases(self):
  r=self.m.find('d'*32,dict(mode=MODES[0],build=25));self.m.db.close();self.m=Matchmaker(clock=lambda:self.t,path=self.path,fleet=self.fleet)
  self.assertEqual(r['address'],self.m.find('d'*32,dict(mode=MODES[0],build=25))['address'])

if __name__=='__main__':unittest.main()
