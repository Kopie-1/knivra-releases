#!/usr/bin/env python3
"""Allow the existing browser-game origin in KNIVRA accounts; preserve all other policies."""
import datetime,hashlib,http.client,os,pathlib,shutil,subprocess,time
TARGET=pathlib.Path('/opt/knivra-server/accounts-web.py')
ORIGIN='https://downloads.knivra.ca'
MARKER="ALLOWED.add('https://downloads.knivra.ca') # KNIVRA browser game"
def updated(source):
 if MARKER in source:return source
 anchor="ALLOWED.update(filter(None,os.environ.get('KNIVRA_EXTRA_ORIGINS','').split(',')))"
 if source.count(anchor)!=1:raise RuntimeError('The account adapter changed; nothing installed.')
 return source.replace(anchor,MARKER+'\n'+anchor,1)
def healthy():
 try:
  c=http.client.HTTPConnection('127.0.0.1',27845,timeout=2);c.request('OPTIONS','/login',headers={'Origin':ORIGIN,'Access-Control-Request-Method':'POST'});r=c.getresponse();ok=r.status==204 and r.getheader('Access-Control-Allow-Origin')==ORIGIN;r.read();c.close();return ok
 except OSError:return False
def main():
 if os.geteuid()!=0:raise SystemExit('Run with sudo python3 '+str(pathlib.Path(__file__).resolve()))
 old=TARGET.read_text();new=updated(old);compile(new,str(TARGET),'exec')
 if old==new and healthy():print('Browser-game sign-in is already enabled.');return
 backup=pathlib.Path('/var/backups/knivra-accounts')/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-browser-origin');backup.mkdir(parents=True,mode=0o700);backup.chmod(0o700);shutil.copy2(TARGET,backup/TARGET.name)
 stat=TARGET.stat();temp=TARGET.with_suffix('.browser23.tmp');temp.write_text(new);temp.chmod(stat.st_mode & 0o777);os.chown(temp,stat.st_uid,stat.st_gid);os.replace(temp,TARGET)
 try:
  subprocess.run(['systemctl','restart','knivra-accounts.service'],check=True)
  for _ in range(15):
   if healthy():print('Browser-game sign-in enabled and origin check passed.');return
   time.sleep(1)
  raise RuntimeError('Account origin check failed.')
 except Exception:
  shutil.copy2(backup/TARGET.name,TARGET);subprocess.run(['systemctl','restart','knivra-accounts.service'],check=False);raise
if __name__=='__main__':main()
