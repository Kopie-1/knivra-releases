#!/usr/bin/env python3
"""Existing Build 25 host upgrade. Verify payload, back up, install, rollback on failure."""
import ast,datetime,hashlib,json,os,pathlib,shutil,subprocess,sys,time,urllib.request
HERE=pathlib.Path(__file__).resolve().parent
TARGETS={'matchmaking.py':'/opt/knivra-server/AccountServer/matchmaking.py','autoscale.py':'/opt/knivra-server/AccountServer/autoscale.py','fleet25.json':'/etc/knivra/fleet25.json','knivra-autoscale.service':'/etc/systemd/system/knivra-autoscale.service','autoscale-accounts.conf':'/etc/systemd/system/knivra-accounts.service.d/zz-autoscale.conf'}
def run(*a):return subprocess.run(a,check=True,capture_output=True,text=True)
def copy(src,dest):
 dest=pathlib.Path(dest);dest.parent.mkdir(parents=True,exist_ok=True);tmp=dest.with_name(dest.name+'.new');shutil.copyfile(src,tmp);tmp.chmod(0o644);tmp.replace(dest)
def main():
 for name,digest in json.loads((HERE/'checksums.json').read_text()).items():
  if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=digest:sys.exit('Checksum mismatch: '+name)
 for name in ('matchmaking.py','autoscale.py'):ast.parse((HERE/name).read_text())
 if '--check' in sys.argv:print('Autoscaling payload validated.');return
 if os.geteuid()!=0:sys.exit('Run this installer with sudo.')
 if not pathlib.Path('/opt/knivra-public/server.pck').exists():sys.exit('Install Build 25 first.')
 if subprocess.run(['systemctl','is-active','--quiet','knivra-autoscale']).returncode==0:sys.exit('Autoscaling is already active. Drain it before upgrading.')
 # Explicit router prerequisite prevents advertising unreachable extra arenas accidentally.
 if '--ports-forwarded' not in sys.argv:sys.exit('Forward UDP 27846–27848 to 192.168.4.93, then run with --ports-forwarded.')
 backup=pathlib.Path('/var/backups/knivra-autoscale')/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');backup.mkdir(parents=True,mode=0o700);backup.parent.chmod(0o700)
 old={}
 for name,dest in TARGETS.items():
  old[name]=pathlib.Path(dest).exists()
  if old[name]:shutil.copy2(dest,backup/name)
 (backup/'targets.json').write_text(json.dumps(TARGETS));(backup/'existing.json').write_text(json.dumps(old))
 firewall_added=False
 try:
  for name,dest in TARGETS.items():copy(HERE/name,dest)
  ufw=shutil.which('ufw')
  if ufw:
   status=run(ufw,'status').stdout
   if 'Status: active' in status and '27846:27848/udp' not in status:
    run(ufw,'allow','27846:27848/udp');firewall_added=True
  run('systemctl','daemon-reload');run('systemctl','restart','knivra-accounts');run('systemctl','enable','--now','knivra-autoscale')
  time.sleep(6)
  for service in ('knivra-accounts','knivra-public','knivra-autoscale'):run('systemctl','is-active','--quiet',service)
  with urllib.request.urlopen('http://127.0.0.1:27845/health',timeout=10) as r:
   if not json.load(r).get('ok'):raise RuntimeError('Accounts health check failed')
 except BaseException:
  subprocess.run(['systemctl','disable','--now','knivra-autoscale'],timeout=1020)
  for name,dest in TARGETS.items():
   if old[name]:copy(backup/name,dest)
   else:pathlib.Path(dest).unlink(missing_ok=True)
  if firewall_added:subprocess.run([ufw,'delete','allow','27846:27848/udp'])
  subprocess.run(['systemctl','daemon-reload']);subprocess.run(['systemctl','restart','knivra-accounts']);raise
 print('Automatic arenas enabled: one always-on arena, up to three extra arenas; 28 human slots maximum.')
 print('Extras start for queued players and stop after reconnect grace plus 120 empty seconds.')
 print('Backup:',backup)
 print('Router reachability must be verified from outside your home network.')
if __name__=='__main__':main()
