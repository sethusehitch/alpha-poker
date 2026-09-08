import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import { safeAvatarUrl, DEFAULT_AVATAR } from '../app/components/characters/avatar.ts';
import { cropGeometry, inspectUpload } from '../app/components/characters/imageCrop.ts';

test('avatar URLs accept only our preset or content-addressed images', () => {
  for (const url of ['https://evil.test/a.png', '//evil.test/a', '/browser-api/avatars/../auth/me', 'javascript:alert(1)']) {
    assert.equal(safeAvatarUrl({id:'bad',url}), DEFAULT_AVATAR.url);
  }
  assert.equal(safeAvatarUrl({id:'bear',url:'/characters/bear.webp'}), '/characters/bear.webp');
  const url = '/browser-api/avatars/' + 'a'.repeat(64);
  assert.equal(safeAvatarUrl({id:'custom',url}), url);
});
test('crop geometry fills the square without gaps at every supported zoom and position', () => {
  for (const [width,height] of [[100,400],[400,100],[512,512]]) {
    for (const zoom of [1,2,3]) for (const x of [0,50,100]) for (const y of [0,50,100]) {
      const b = cropGeometry({url:'',width,height},zoom,x,y,512);
      assert.ok(b.left <= 0 && b.top <= 0);
      assert.ok(b.left+b.width >= 512 && b.top+b.height >= 512);
    }
  }
});
test('upload rejects non-images and oversized files before browser decoding', async () => {
  await assert.rejects(inspectUpload(new File(['<svg/>'],'x.svg')), /valid JPG/);
  await assert.rejects(inspectUpload(new File([new Uint8Array(2097153)],'x.png')), /2 MB/);
});
test('offline recap disables avatar lookup and packages its relative fallback', async () => {
  const source = await readFile(new URL('../app/components/characters/CharacterImage.tsx', import.meta.url), 'utf8');
  assert.match(source, /if \(offline\) return;/);
  assert.match(source, /offline \? DEFAULT_AVATAR.url.slice\(1\)/);
  const viewer = await readFile(new URL('../local-viewer/main.tsx', import.meta.url), 'utf8');
  assert.match(viewer, /OfflineCharacters.Provider value=\{true\}/);
  const packaging = await readFile(new URL('../cli/pyproject.toml', import.meta.url), 'utf8');
  assert.match(packaging, /viewer\/characters\/\*/);
});
test('both hosted policies permit local crop previews without external image hosts', async () => {
  for (const file of ['Caddyfile','Caddyfile.aws']) {
    const source = await readFile(new URL('../'+file,import.meta.url),'utf8');
    assert.match(source, /img-src 'self' data: blob: https:\/\/fastapi.tiangolo.com;/);
  }
});
