import base64
import io
import sqlite3
import struct
import zlib
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from PIL import Image, PngImagePlugin

from alpha_poker_api.avatars import MAX_BODY_BYTES, MAX_IMAGE_BYTES, avatar_for
from alpha_poker_api import avatars as avatar_module
from alpha_poker_api.db import Database
from test_auth import auth_client, package


def register(client, username='avatar_owner'):
    response = client.post('/v1/auth/register', json={'username': username, 'password': 'correct horse'})
    assert response.status_code == 201
    return {'Authorization': f"Bearer {response.json()['token']}"}


def picture(fmt='PNG', color='red', size=(64, 32)):
    image = Image.new('RGB', size, color)
    output = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text('private', 'secret GPS metadata')
    image.save(output, format=fmt, pnginfo=metadata)
    mime = {'PNG': 'png', 'JPEG': 'jpeg', 'WEBP': 'webp', 'GIF': 'gif'}[fmt]
    return f'data:image/{mime};base64,' + base64.b64encode(output.getvalue()).decode()


def test_default_selection_account_isolation_and_restart(tmp_path):
    with auth_client(tmp_path) as client:
        owner = register(client)
        other = register(client, 'other_owner')
        assert client.get('/v1/account/avatar').status_code == 401
        assert client.put('/v1/account/avatar', json={'preset': 'bear'}).status_code == 401
        assert client.get('/v1/account/avatar', headers=owner).json()['avatar']['id'] == 'elephant'
        for preset in ('bear', 'octopus', 'bird', 'elephant'):
            assert client.put('/v1/account/avatar', headers=owner, json={'preset': preset}).json() == {
                'avatar': {'id': preset, 'url': f'/characters/{preset}.webp'}}
        client.put('/v1/account/avatar', headers=owner, json={'preset': 'bear'})
        assert client.get('/v1/auth/me', headers=owner).json()['avatar']['id'] == 'bear'
        assert client.get('/v1/account/status', headers=owner).json()['avatar']['id'] == 'bear'
        assert client.get('/v1/account/avatar', headers=other).json()['avatar']['id'] == 'elephant'
        # Private registered accounts are not enumerated through public lookup.
        assert client.get('/v1/avatars/users/avatar_owner').status_code == 404
        assert client.get('/v1/avatars/users/missing').status_code == 404
    with auth_client(tmp_path) as client:
        assert client.get('/v1/account/avatar', headers=owner).json()['avatar']['id'] == 'bear'


@pytest.mark.parametrize('fmt', ['PNG', 'JPEG', 'WEBP'])
def test_upload_sanitized_image(fmt, tmp_path):
    with auth_client(tmp_path) as client:
        headers = register(client)
        response = client.put('/v1/account/avatar', headers=headers, json={'image_data': picture(fmt)})
        assert response.status_code == 200, response.text
        avatar = response.json()['avatar']
        assert len(avatar['id']) == 64
        assert avatar['url'] == '/browser-api/avatars/' + avatar['id']
        public = client.get('/v1/avatars/' + avatar['id'])
        assert public.status_code == 200
        assert public.headers['content-type'] == 'image/webp'
        assert public.headers['x-content-type-options'] == 'nosniff'
        with Image.open(io.BytesIO(public.content)) as processed:
            assert processed.size == (512, 512)
            assert processed.format == 'WEBP'
            assert not processed.getexif()
            assert 'private' not in processed.info
        assert b'secret GPS' not in public.content


def test_custom_replacement_is_bounded_and_preserves_other_account(tmp_path):
    with auth_client(tmp_path) as client:
        headers = register(client)
        other = register(client, 'other_owner')
        first = client.put('/v1/account/avatar', headers=headers, json={'image_data': picture()}).json()['avatar']
        shared = client.put('/v1/account/avatar', headers=other, json={'image_data': picture()}).json()['avatar']
        assert first == shared
        client.put('/v1/account/avatar', headers=headers, json={'preset': 'bird'})
        assert client.get('/v1/avatars/' + first['id']).status_code == 200
        second = client.put('/v1/account/avatar', headers=headers, json={'image_data': picture(color='blue')}).json()['avatar']
        assert second != first
        assert client.get('/v1/avatars/' + first['id']).status_code == 200
        assert client.get('/v1/account/avatar', headers=other).json()['avatar'] == first
        client.put('/v1/account/avatar', headers=other, json={'image_data': picture(color='green')})
        assert client.get('/v1/avatars/' + first['id']).status_code == 404
        assert client.app.state.db.one('SELECT count(*) n FROM account_avatars')['n'] == 2
        assert client.get('/v1/avatars/not-a-hash').status_code == 404


@pytest.mark.parametrize('payload', [
    {'preset': 'dragon'}, {'preset': ['bear']}, {'preset': 'custom'}, {}, [],
    {'preset': 'bear', 'username': 'other_owner'},
    {'preset': 'bear', 'image_data': 'x'}, {'image_data': None},
    {'image_data': 'data:image/svg+xml;base64,PHN2Zy8+'},
    {'image_data': 'data:image/png;base64,bm90IGFuIGltYWdl'},
    {'image_data': 'data:image/png;base64,==='},
])
def test_bad_requests_leave_selection_intact(payload, tmp_path):
    with auth_client(tmp_path) as client:
        headers = register(client)
        client.put('/v1/account/avatar', headers=headers, json={'preset': 'bear'})
        assert client.put('/v1/account/avatar', headers=headers, json=payload).status_code in (400, 413)
        assert client.get('/v1/account/avatar', headers=headers).json()['avatar']['id'] == 'bear'


def test_oversized_malformed_mismatched_animated_images(tmp_path):
    with auth_client(tmp_path) as client:
        headers = register(client)
        assert client.put('/v1/account/avatar', headers=headers, content=b'x' * (MAX_BODY_BYTES + 1)).status_code == 413
        assert client.put('/v1/account/avatar', headers=headers, content=b'{').status_code == 400
        too_big = 'data:image/png;base64,' + base64.b64encode(b'x' * (MAX_IMAGE_BYTES + 1)).decode()
        assert client.put('/v1/account/avatar', headers=headers, json={'image_data': too_big}).status_code == 413
        assert client.put('/v1/account/avatar', headers=headers, json={'image_data': picture(size=(4097, 1))}).status_code == 400
        assert client.put('/v1/account/avatar', headers=headers, json={'image_data': picture('JPEG').replace('image/jpeg', 'image/png')}).status_code == 400
        animated = io.BytesIO()
        Image.new('RGB', (8, 8), 'red').save(animated, format='PNG', save_all=True, append_images=[Image.new('RGB', (8, 8), 'blue')])
        value = 'data:image/png;base64,' + base64.b64encode(animated.getvalue()).decode()
        assert client.put('/v1/account/avatar', headers=headers, json={'image_data': value}).status_code == 400
        # Forge dimensions in the PNG header without allocating a giant image.
        raw = bytearray(base64.b64decode(picture().split(',')[1]))
        raw[16:24] = struct.pack('>II', 100000, 100000)
        raw[29:33] = struct.pack('>I', zlib.crc32(raw[12:29]))
        bomb = 'data:image/png;base64,' + base64.b64encode(raw).decode()
        assert client.put('/v1/account/avatar', headers=headers, json={'image_data': bomb}).status_code == 400


def test_bot_replacement_preserves_avatar(tmp_path):
    with auth_client(tmp_path) as client:
        headers = register(client)
        client.put('/v1/account/avatar', headers=headers, json={'preset': 'octopus'})
        for index in range(2):
            response = client.post('/v1/submissions', headers={**headers, 'Idempotency-Key': f'avatar-upload-{index}'}, data={'bot_name': f'Avatar Bot {index}'}, files={'package': ('bot.zip', package(), 'application/zip')})
            assert response.status_code == 202, response.text
            assert client.get('/v1/account/avatar', headers=headers).json()['avatar']['id'] == 'octopus'


def test_additive_migration_and_seeded_default(tmp_path):
    path = tmp_path / 'legacy.sqlite3'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE users(username TEXT PRIMARY KEY,password_hash TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)')
        conn.execute("INSERT INTO users VALUES('existing','hash','old','old')")
    db = Database(path)
    db.initialize(seed=True)
    db.initialize(seed=True)
    assert db.one("SELECT password_hash FROM users WHERE username='existing'")['password_hash'] == 'hash'
    assert avatar_for(db, 'existing')['id'] == 'elephant'
    seeded = db.one('SELECT username FROM leaderboard LIMIT 1')
    assert avatar_for(db, seeded['username'])['id'] == 'elephant'


def test_public_leaderboard_and_rivals_use_current_account_selection(client):
    entry = client.get('/v1/leaderboard').json()['entries'][0]
    username = entry['username']
    assert entry['avatar']['id'] == 'elephant'
    assert client.get('/v1/avatars/users/' + username).json()['avatar'] == entry['avatar']
    headers = register(client, username)
    client.put('/v1/account/avatar', headers=headers, json={'preset': 'bird'})
    assert client.get('/v1/leaderboard').json()['entries'][0]['avatar']['id'] == 'bird'
    assert client.get('/v1/avatars/users/' + username).json()['avatar']['id'] == 'bird'
    viewer = register(client, 'avatar_viewer')
    detail = client.get('/v1/rivals/' + username, headers=viewer).json()
    assert detail['rival']['avatar']['id'] == 'bird'
    assert detail['viewer']['avatar']['id'] == 'elephant'


def test_upload_rate_limit(tmp_path):
    with auth_client(tmp_path) as client:
        headers = register(client)
        for _ in range(10):
            assert client.put('/v1/account/avatar', headers=headers, json={'image_data': picture()}).status_code == 200
        assert client.put('/v1/account/avatar', headers=headers, json={'image_data': picture()}).status_code == 429
        assert client.put('/v1/account/avatar', headers=headers, json={'preset': 'bird'}).status_code == 200


def test_busy_uploads_reject_instead_of_buffering_more_requests(tmp_path, monkeypatch):
    entered = threading.Barrier(3)
    release = threading.Event()
    original = avatar_module.process_image

    def slow_process(value):
        entered.wait(timeout=10)
        assert release.wait(timeout=10)
        return original(value)

    monkeypatch.setattr(avatar_module, 'process_image', slow_process)
    with auth_client(tmp_path) as client, ThreadPoolExecutor(max_workers=2) as pool:
        headers = register(client)
        futures = [pool.submit(client.put, '/v1/account/avatar', headers=headers, json={'image_data': picture()}) for _ in range(2)]
        try:
            entered.wait(timeout=10)
            assert client.put('/v1/account/avatar', headers=headers, json={'image_data': picture()}).status_code == 429
        finally:
            release.set()
        assert all(future.result(timeout=10).status_code == 200 for future in futures)


def test_batch_avatar_reads_are_bounded_and_exclude_blobs(client, monkeypatch):
    db = client.app.state.db
    statements = []
    original = db.all

    def tracked(sql, parameters=()):
        statements.append((sql, len(parameters)))
        return original(sql, parameters)

    monkeypatch.setattr(db, 'all', tracked)
    descriptors = avatar_module.avatars_for(db, (f'user_{index}' for index in range(601)))
    assert len(descriptors) == 601
    assert len(statements) == 2
    assert all(count <= 500 and 'custom_image' not in sql for sql, count in statements)


def test_participant_descriptor_stays_consistent_across_all_surfaces(client):
    names = [entry['username'] for entry in client.get('/v1/leaderboard').json()['entries'][:2]]
    owner, opponent = [register(client, name) for name in names]
    for headers in (owner, opponent):
        uploaded = client.post('/v1/submissions', headers=headers, data={'bot_name': 'Avatar QA Bot'}, files={'package': ('bot.zip', package(), 'application/zip')})
        assert uploaded.status_code == 202, uploaded.text
    challenge = client.post('/v1/challenges', headers=owner, json={'opponent_username': names[1]})
    assert challenge.status_code == 201, challenge.text
    challenge_id = challenge.json()['challenge_id']
    # Updating the account must update every existing participant view, including
    # previously created challenges, without needing a new competition result.
    for selection in ({'image_data': picture()}, {'preset': 'octopus'}):
        expected = client.put('/v1/account/avatar', headers=owner, json=selection).json()['avatar']
        for path in ('/v1/account/avatar', '/v1/account/status', '/v1/auth/me'):
            assert client.get(path, headers=owner).json()['avatar'] == expected
        assert client.get('/v1/avatars/users/' + names[0]).json()['avatar'] == expected
        standings = client.get('/v1/leaderboard').json()['entries']
        assert next(row for row in standings if row['username'] == names[0])['avatar'] == expected
        rivals = client.get('/v1/rivals?source=leaderboard', headers=opponent).json()['items']
        assert next(row for row in rivals if row['username'] == names[0])['avatar'] == expected
        assert client.get('/v1/rivals/' + names[0], headers=opponent).json()['rival']['avatar'] == expected
        detail = client.get('/v1/challenges/' + challenge_id, headers=opponent).json()
        assert detail['challenger_avatar'] == detail['opponent_avatar'] == expected
        assert detail['challenged_avatar']['id'] == 'elephant'
        listed = client.get('/v1/challenges', headers=opponent).json()['items']
        assert next(row for row in listed if row['challenge_id'] == challenge_id)['challenger_avatar'] == expected


def test_exact_decoded_limit_fits_api_and_browser_json_caps(tmp_path):
    import json

    raw = base64.b64decode(picture().split(',')[1])
    # Trailing bytes are stripped by image reencoding. Pad a real PNG to the exact
    # decoded byte limit so the base64/JSON overhead boundary is exercised.
    raw += b'\0' * (MAX_IMAGE_BYTES - len(raw))
    payload = json.dumps({'image_data': 'data:image/png;base64,' + base64.b64encode(raw).decode()})
    assert len(payload.encode()) <= MAX_BODY_BYTES < 3 * 1024 * 1024
    with auth_client(tmp_path) as client:
        headers = register(client)
        response = client.put('/v1/account/avatar', headers=headers, content=payload)
        assert response.status_code == 200, response.text
        public = client.get('/v1/avatars/' + response.json()['avatar']['id'])
        assert len(public.content) < 10000
        # The stricter API bound remains enforced for proxy-accepted requests.
        between_caps = b' ' * (MAX_BODY_BYTES + 1)
        assert len(between_caps) < 3 * 1024 * 1024
        assert client.put('/v1/account/avatar', headers=headers, content=between_caps).status_code == 413
