"""Extracted starter kit -> offline training -> local recap -> authenticated sync.

Uses only a new temporary directory and loopback API. No production state.
Run after build_starter_kit: PYTHONPATH=server:cli server/.venv/bin/python qa/dojo_smoke.py
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import Request, urlopen
import zipfile

root = Path(__file__).resolve().parents[1]
work = Path(tempfile.mkdtemp(prefix="alpha-dojo-smoke-"))
kit = work/'kit'
with zipfile.ZipFile(root/'public/alpha-poker-starter.zip') as archive:
    public_engine = {name.removeprefix('cli/alpha_poker_cli/dojo_engine/') for name in archive.namelist() if '/dojo_engine/' in name}
    assert public_engine == {'__init__.py','engine.py','evaluator.py','dojo.py','dojo_catalog.json'}
    assert not any('/submissions/' in n or '/uploads/' in n for n in archive.namelist())
    archive.extractall(kit)
# Deliberately simple test strategy chosen to beat the first check/fold bot.
(kit/'bot.py').write_text("def decide(s):\n    if 'raise' in s['legal_actions']: return {'action':'raise','amount':s['min_raise_to']}\n    return {'action':'check' if 'check' in s['legal_actions'] else 'call'}\n")
env = {**os.environ, 'PYTHONPATH':str(kit/'cli'), 'ALPHA_POKER_CONFIG':str(work/'credentials.json'),
    'ALPHA_POKER_DOJO_STATE':str(work/'dojo.json'), 'ALPHA_POKER_RECAP_STATE':str(work/'latest.json'),
    'ALPHA_POKER_API_URL':'http://127.0.0.1:1/v1'}

def cli(*args):
    process = subprocess.run([sys.executable,'-m','alpha_poker_cli',*args], cwd=kit, env=env,
        capture_output=True,text=True,timeout=180)
    if process.returncode:
        raise RuntimeError(process.stderr + process.stdout)
    return process.stdout

listed = json.loads(cli('dojo','list','--offline','--json'))
assert len(listed['bots']) == 5
for opponent in listed['bots']:
    hands = '200' if opponent['id']=='pebble' else '4'
    assert 'Training complete' in cli('train','.', '--opponent',opponent['id'],'--hands',hands,'--output',str(work/f"{opponent['id']}.zip"))
    with zipfile.ZipFile(work/f"{opponent['id']}.zip") as archive:
        summary = json.loads(archive.read('summary.json'))
        assert summary['bot_errors'] == 0
        assert summary['hands_played'] == int(hands)
        if opponent['id']=='pebble':
            first = summary
assert first['qualified']
replay = cli('recap',str(work/'pebble.zip'))
url = next(line.removeprefix('Local recap: ') for line in replay.splitlines() if line.startswith('Local recap: '))
with urlopen(url+'manifest.json') as response:
    assert len(json.load(response)['groups'][0]['hands']) == 200
with urlopen(url+'recap/0/199') as response:
    hand = json.load(response)['highlights'][0]
    assert hand['hand_number'] == 200 and hand['steps']

os.environ.update({'ALPHA_POKER_DATA_DIR':str(work/'db'),'ALPHA_POKER_SEED':'false',
    'ALPHA_POKER_AUTO_RUN':'false','ALPHA_POKER_AUTH_REQUIRED':'true'})
from alpha_poker_api.main import app
import uvicorn
sock = socket.socket()
sock.bind(('127.0.0.1',0))
api = f'http://127.0.0.1:{sock.getsockname()[1]}/v1'
server = uvicorn.Server(uvicorn.Config(app,log_level='error'))
thread = threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True)
thread.start()
deadline = time.monotonic()+15
while not server.started:
    if not thread.is_alive() or time.monotonic()>deadline:
        raise RuntimeError('Local API did not start')
    time.sleep(.05)
try:
    with urlopen(Request(api+'/auth/register',data=json.dumps({'username':'dojo-smoke','password':'local-fixture-only-password'}).encode(),headers={'Content-Type':'application/json'})) as response:
        account=json.load(response)
    credentials=work/'credentials.json'
    credentials.write_text(json.dumps({'profiles':{api:{'username':account['username'],'token':account['token']}}}))
    credentials.chmod(0o600)
    for _ in range(2):
        result=json.loads(cli('dojo','sync',first['run_id'],'--api-url',api,'--json'))
        assert result['beaten'] and result['verification']=='self_reported'
    with urlopen(Request(api+'/dojo/progress',headers={'Authorization':'Bearer '+account['token']})) as response:
        assert json.load(response)['progress']['pebble']=={'beaten':True,'runs':1}
finally:
    server.should_exit=True
    thread.join(10)
    sock.close()
print(json.dumps({'evidence':str(work),'viewer':url,'offline_opponents':5,'mirrored_hands':200,'account_sync':'passed','kit_isolated':True}))
