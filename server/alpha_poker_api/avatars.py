"""Account-owned, bounded and sanitized public avatar images."""
from __future__ import annotations

import base64
import asyncio
import binascii
import hashlib
import io
import json
import re
from collections.abc import Iterable

from fastapi import FastAPI, Header, HTTPException, Request, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from .auth import require_user
from .db import Database, now_iso
from .ratelimit import RateLimiter

PRESETS = frozenset(('elephant', 'bear', 'octopus', 'bird'))
MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_BODY_BYTES = ((MAX_IMAGE_BYTES + 2) // 3) * 4 + 1024
MAX_DIMENSION = 4096
MAX_PIXELS = 4096 * 4096


def avatar_for(db: Database, username: str) -> dict[str, str]:
    row = db.one('SELECT preset,custom_id FROM account_avatars WHERE username=?', (username,))
    return avatar_descriptor(row)


def avatars_for(db: Database, usernames: Iterable[str]) -> dict[str, dict[str, str]]:
    names = list(set(usernames))
    result = {name: avatar_descriptor(None) for name in names}
    for offset in range(0, len(names), 500):
        batch = names[offset:offset + 500]
        rows = db.all('SELECT username,preset,custom_id FROM account_avatars WHERE username IN (' + ','.join('?' for _ in batch) + ')', tuple(batch))
        result.update({row['username']: avatar_descriptor(row) for row in rows})
    return result


def avatar_descriptor(row: dict | None) -> dict[str, str]:
    if row and row['preset'] == 'custom' and row['custom_id']:
        return {'id': row['custom_id'], 'url': f"/browser-api/avatars/{row['custom_id']}"}
    preset = row['preset'] if row and row['preset'] in PRESETS else 'elephant'
    return {'id': preset, 'url': f'/characters/{preset}.webp'}


def process_image(value: object) -> bytes:
    if not isinstance(value, str):
        raise HTTPException(400, 'image_data must be a data URL string')
    if len(value) > MAX_BODY_BYTES:
        raise HTTPException(413, 'Avatar image is too large')
    match = re.fullmatch(r'data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)', value)
    if not match:
        raise HTTPException(400, 'Use a PNG, JPEG, or WebP image')
    try:
        raw = base64.b64decode(match[2], validate=True)
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(413, 'Avatar image must be at most 2 MiB')
        with Image.open(io.BytesIO(raw)) as source:
            if source.format != {'png': 'PNG', 'jpeg': 'JPEG', 'webp': 'WEBP'}[match[1]]:
                raise ValueError('Image type does not match')
            width, height = source.size
            if min(width, height) < 1 or max(width, height) > MAX_DIMENSION or width * height > MAX_PIXELS:
                raise ValueError('Image dimensions exceed 4096 pixels')
            if getattr(source, 'n_frames', 1) != 1:
                raise ValueError('Animated images are not supported')
            source.verify()
        with Image.open(io.BytesIO(raw)) as source:
            source.load()
            # Crop/resize before orientation and RGBA conversion so those operations
            # never allocate additional full-resolution image buffers.
            cropped = ImageOps.exif_transpose(ImageOps.fit(source, (512, 512), method=Image.Resampling.LANCZOS)).convert('RGBA')
            # A fresh image prevents metadata, profiles, and EXIF from being copied.
            clean = Image.new('RGBA', (512, 512))
            clean.paste(cropped)
            output = io.BytesIO()
            clean.save(output, format='WEBP', quality=90, method=4)
            return output.getvalue()
    except (ValueError, binascii.Error, OSError, SyntaxError, EOFError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise HTTPException(400, 'Invalid image. Use a still PNG, JPEG, or WebP up to 4096 pixels per side') from exc


def register_avatar_routes(app: FastAPI, db: Database) -> None:
    upload_limiter = RateLimiter()
    image_slots = asyncio.Semaphore(2)
    @app.get('/v1/account/avatar')
    def get_avatar(authorization: str | None = Header(None)):
        return {'avatar': avatar_for(db, require_user(db, authorization))}

    @app.put('/v1/account/avatar')
    async def set_avatar(request: Request, authorization: str | None = Header(None)):
        username = require_user(db, authorization)
        # Do not queue unlimited multi-megabyte bodies while decode slots are busy.
        if image_slots.locked():
            raise HTTPException(429, 'Avatar uploads are busy. Try again shortly')
        async with image_slots:
            return await save_avatar(request, username)

    async def save_avatar(request: Request, username: str):
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_BODY_BYTES:
                raise HTTPException(413, 'Avatar request is too large')
            body.extend(chunk)
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(400, 'Invalid JSON') from exc
        if not isinstance(payload, dict) or set(payload) not in ({'preset'}, {'image_data'}):
            raise HTTPException(400, 'Provide exactly one of preset or image_data')
        if 'preset' in payload:
            preset = payload['preset']
            if not isinstance(preset, str) or preset not in PRESETS:
                raise HTTPException(400, 'Unknown character preset')
            db.execute('INSERT INTO account_avatars(username,preset,updated_at) VALUES(?,?,?) '
                       'ON CONFLICT(username) DO UPDATE SET preset=excluded.preset,updated_at=excluded.updated_at',
                       (username, preset, now_iso()))
        else:
            if not upload_limiter.allow(username, 10, 60):
                raise HTTPException(429, 'Too many image uploads. Try again in a minute')
            processed = await run_in_threadpool(process_image, payload['image_data'])
            content_id = hashlib.sha256(processed).hexdigest()
            db.execute('INSERT INTO account_avatars(username,preset,custom_id,custom_image,updated_at) VALUES(?,?,?,?,?) '
                       'ON CONFLICT(username) DO UPDATE SET preset=excluded.preset,custom_id=excluded.custom_id,'
                       'custom_image=excluded.custom_image,updated_at=excluded.updated_at',
                       (username, 'custom', content_id, processed, now_iso()))
        return {'avatar': avatar_for(db, username)}

    @app.get('/v1/avatars/users/{username}')
    def public_user_avatar(username: str):
        # Only participants already exposed by public league data are discoverable.
        if not db.one('SELECT 1 FROM leaderboard WHERE username=? UNION SELECT 1 FROM submissions WHERE username=? AND active=1 LIMIT 1', (username, username)):
            raise HTTPException(404, 'Participant not found')
        return {'avatar': avatar_for(db, username)}

    @app.get('/v1/avatars/{content_id}')
    def public_image(content_id: str):
        if not re.fullmatch(r'[a-f0-9]{64}', content_id):
            raise HTTPException(404, 'Avatar not found')
        row = db.one('SELECT custom_image FROM account_avatars WHERE custom_id=? LIMIT 1', (content_id,))
        if not row:
            raise HTTPException(404, 'Avatar not found')
        return Response(bytes(row['custom_image']), media_type='image/webp', headers={
            'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'public, max-age=31536000, immutable',
            'Content-Security-Policy': "default-src 'none'", 'ETag': f'"{content_id}"',
        })
