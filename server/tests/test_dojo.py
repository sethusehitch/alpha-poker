import pytest
from alpha_poker.dojo import VERSION, IDS, catalog


def login(client, username):
    result = client.post('/v1/auth/register', json={'username': username, 'password': 'local-test-password'})
    assert result.status_code == 201
    return {'Authorization': 'Bearer ' + result.json()['token']}


def payload(**changes):
    return dict(run_id='dojo_'+'a'*24, opponent='pebble', opponent_version=VERSION,
        bot_sha256='0'*64, hands_played=200, net_chips=10, bot_errors=0, seed=123, **changes)


def test_dojo_catalog_never_exposes_leader_code(client):
    data = client.get('/v1/dojo/opponents').json()
    assert [b['id'] for b in data['bots']] == list(IDS)
    assert data['leader'] is None  # sample leaderboard is not a runnable leader
    assert 'submission' not in str(data)
    assert 'package_path' not in str(data)


def test_leader_menu_uses_real_standing_without_private_metadata(client):
    db = client.app.state.db
    db.execute("INSERT INTO submissions(id,username,bot_name,original_filename,package_path,sha256,status,active,created_at,updated_at) "
        "VALUES('private-leader','maya','Actual Leader','private.zip','/private/source-do-not-expose','secret-digest','accepted',1,'2026-01-01','2026-01-01')")
    db.execute("UPDATE leaderboard SET submission_id='private-leader',bot_name='Actual Leader' WHERE run_id='run_demo' AND rank=1")
    data = client.get('/v1/dojo/opponents').json()
    assert data['leader'] == {'username':'maya','bot_name':'Actual Leader','elo_rating':1264}
    assert 'private-leader' not in str(data)
    assert 'source-do-not-expose' not in str(data)
    assert 'secret-digest' not in str(data)
    session = client.post('/v1/training/sessions', json={'username':'student','opponent':'leader','hand_limit':2}).json()
    assert db.one('SELECT leader_username,leader_submission_id FROM training_sessions WHERE id=?', (session['session_id'],)) == {'leader_username':'maya','leader_submission_id':'private-leader'}


def test_private_self_reported_progress_is_idempotent_and_no_elo_effect(client):
    alice, bob = login(client, 'dojo-alice'), login(client, 'dojo-bob')
    before = client.get('/v1/leaderboard').json()
    assert client.get('/v1/dojo/progress').status_code == 401
    assert client.post('/v1/dojo/results', json=payload()).status_code == 401
    for _ in range(2):
        result = client.post('/v1/dojo/results', json=payload(), headers=alice)
        assert result.status_code == 200
        assert result.json()['verification'] == 'self_reported'
    progress = client.get('/v1/dojo/progress', headers=alice).json()['progress']
    assert progress['pebble'] == {'beaten': True, 'runs': 1}
    assert not client.get('/v1/dojo/progress', headers=bob).json()['progress']['pebble']['beaten']
    conflicting = {**payload(), 'net_chips': 11}
    assert client.post('/v1/dojo/results', json=conflicting, headers=alice).status_code == 409
    assert client.get('/v1/leaderboard').json() == before


@pytest.mark.parametrize('change', [
    {'opponent': 'leader'}, {'username': 'someone-else'}, {'hands_played': 201},
    {'hands_played': True}, {'hands_played': 402}, {'net_chips': 800001},
    {'hands_played': 2, 'net_chips': 5000}, {'bot_errors': -1}, {'seed': -1},
    {'run_id': '../path'}, {'bot_sha256': 'not-a-hash'}])
def test_invalid_dojo_results_rejected(client, change):
    headers = login(client, 'dojo-invalid')
    assert client.post('/v1/dojo/results', json={**payload(), **change}, headers=headers).status_code == 422


@pytest.mark.parametrize('change', [{'net_chips': 0}, {'net_chips': -100}, {'hands_played': 198}, {'bot_errors': 1}])
def test_incomplete_or_unsuccessful_practice_does_not_earn_checkmark(client, change):
    headers = login(client, 'dojo-practice')
    response = client.post('/v1/dojo/results', json={**payload(), **change}, headers=headers)
    assert response.status_code == 200
    assert response.json()['beaten'] is False


def test_old_version_is_not_current_progress(client):
    headers = login(client, 'dojo-version')
    assert client.post('/v1/dojo/results', json={**payload(), 'opponent_version': 'dojo-old'}, headers=headers).status_code == 409


def test_catalog_has_exactly_five_public_strategies():
    assert len(catalog()['bots']) == 5
    import json
    from pathlib import Path
    report = json.loads((Path(__file__).resolve().parents[2]/'qa/dojo-calibration.json').read_text())
    ids = [b['id'] for b in catalog()['bots']]
    for run in ('calibration', 'validation'):
        assert sorted(ids, key=report[run]['ratings'].get) == ids
        assert sum(row['errors'] for row in report[run]['matchups']) == 0
    assert {b['id']:b['rating'] for b in catalog()['bots']} == report['calibration']['ratings']


def test_summit_version_does_not_retire_other_opponents(client):
    from alpha_poker.dojo import opponent_version
    headers = login(client, 'dojo-per-opponent')
    assert client.post('/v1/dojo/results', json=payload(), headers=headers).status_code == 200
    old = {**payload(), 'run_id': 'dojo_'+'b'*24, 'opponent': 'summit'}
    client.app.state.db.execute('INSERT INTO dojo_results VALUES(?,?,?,?,?,?,?)',
        ('dojo-per-opponent', old['run_id'], 'summit', VERSION, '{}', 1, '2026-09-08'))
    assert client.post('/v1/dojo/results', json=old, headers=headers).status_code == 409
    progress = client.get('/v1/dojo/progress', headers=headers).json()['progress']
    assert progress['pebble'] == {'beaten': True, 'runs': 1}
    assert progress['summit'] == {'beaten': False, 'runs': 0}
    current = {**old, 'run_id': 'dojo_'+'c'*24, 'opponent_version': opponent_version('summit')}
    assert client.post('/v1/dojo/results', json=current, headers=headers).status_code == 200
    progress = client.get('/v1/dojo/progress', headers=headers).json()['progress']
    assert progress['summit'] == {'beaten': True, 'runs': 1}
    assert client.app.state.db.one('SELECT COUNT(*) AS n FROM dojo_results WHERE username=?',
        ('dojo-per-opponent',))['n'] == 3


def test_packaged_summit_instances_have_separate_memory(monkeypatch):
    import alpha_poker.dojo as module
    def record(state, memory):
        memory['calls'] = memory.get('calls', 0) + 1
        return {'action': 'check'}
    monkeypatch.setattr(module, 'summit_decide', record)
    first, second = module.PackagedBot('summit'), module.PackagedBot('summit')
    first.decide({})
    second.decide({})
    first.decide({})
    assert first._memory == {'calls': 2}
    assert second._memory == {'calls': 1}


def test_generated_dojo_sources_match_server_and_starter():
    from pathlib import Path
    import zipfile
    root = Path(__file__).resolve().parents[2]
    names = ['engine.py', 'evaluator.py', 'dojo.py', 'summit_policy.py', 'dojo_catalog.json']
    with zipfile.ZipFile(root/'public/alpha-poker-starter.zip') as archive:
        for name in names:
            expected = (root/'server/alpha_poker'/name).read_bytes()
            assert (root/'cli/alpha_poker_cli/dojo_engine'/name).read_bytes() == expected
            assert archive.read('cli/alpha_poker_cli/dojo_engine/'+name) == expected
