import assert from 'node:assert/strict';
import test from 'node:test';
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
