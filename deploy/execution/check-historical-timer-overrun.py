"""Real isolated user-systemd overrun regression; never operates production units."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid


def command(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def check(defer, root):
    name = 'dehps-historical-timer-839-' + uuid.uuid4().hex
    probe = root / (name + '.py')
    probe.write_text('''import json,sys,time
def event(kind):
    print(json.dumps({'kind':kind,'at':time.time()}),flush=True)
event(sys.argv[1]+'-start')
if sys.argv[1]=='publisher':time.sleep(6)
event(sys.argv[1]+'-end')
''')
    units = [name+'.timer', name+'.service', name+'-worker.service']
    try:
        command('systemd-run', '--user', '--quiet', '--collect', '--unit='+name,
                '--on-calendar=*:*:0/4', '--timer-property=AccuracySec=1ms',
                '--timer-property=DeferReactivation='+str(defer).lower(),
                '--property=Type=oneshot', '/usr/bin/python3', str(probe), 'publisher')
        deadline = time.monotonic()+40
        worker = False
        while time.monotonic()<deadline:
            journal=command('journalctl','--user','--no-pager','-o','cat',
                            '-u',name+'.service','-u',name+'-worker.service')
            events=[json.loads(x) for x in journal.splitlines() if x.startswith('{"kind":')]
            if events and not worker:
                command('systemd-run', '--user', '--quiet', '--collect', '--no-block',
                        '--unit='+name+'-worker', '--property=Type=oneshot',
                        '--property=After='+name+'.service',
                        '/usr/bin/python3', str(probe), 'worker')
                worker = True
            starts = [x['at'] for x in events if x['kind']=='publisher-start']
            ends = [x['at'] for x in events if x['kind']=='publisher-end']
            workers = [x['at'] for x in events if x['kind']=='worker-start']
            if len(starts)>=2 and ends and (workers or not defer):
                gap = starts[1]-ends[0]
                assert gap>0.5 if defer else gap<0.5, (defer,gap,events)
                if defer:assert ends[0]<=workers[0]<starts[1], events
                return {'defer':defer, 'gap_seconds':gap, 'events':events,
                        'dependent_handoff':bool(workers and ends[0]<=workers[0]<starts[1])}
            time.sleep(0.1)
        raise RuntimeError('Isolated systemd timer did not produce two starts: '+json.dumps(events))
    finally:
        subprocess.run(['systemctl','--user','stop',*units],capture_output=True)
        subprocess.run(['systemctl','--user','reset-failed',*units],capture_output=True)


if __name__=='__main__':
    assert os.getuid()!=0, 'Run as the ordinary user, not root'
    version=command('systemctl','--version').splitlines()[0]
    assert int(version.split()[1])>=257, 'DeferReactivation requires systemd257+'
    with tempfile.TemporaryDirectory(prefix='dehps-historical-timer-839-') as folder:
        results=[check(defer,Path(folder)) for defer in (False,True)]
    print(json.dumps({'systemd':version,'results':results,'status':'PASSED'},indent=2))
