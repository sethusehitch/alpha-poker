import test from "node:test";
import assert from "node:assert/strict";
import { publicRequestUrl, samePublicOrigin } from "../app/browser-api/publicOrigin.mjs";

test("TLS-terminated canonical requests match HTTPS origin, not HTTP", () => {
  const request = origin => new Request("http://alphapoker.io/browser-api/auth/google/start", {headers:{origin}});
  assert.equal(samePublicOrigin(request("https://alphapoker.io")), true);
  assert.equal(samePublicOrigin(request("http://alphapoker.io")), false);
  assert.equal(samePublicOrigin(request("https://evil.invalid")), false);
  assert.equal(publicRequestUrl(request("https://alphapoker.io").url).protocol, "https:");
});
test("localhost stays HTTP and forwarding headers cannot change the origin", () => {
  assert.equal(samePublicOrigin(new Request("http://localhost:3001/test", {headers:{origin:"http://localhost:3001"}})), true);
  assert.equal(samePublicOrigin(new Request("http://localhost:3001/test", {headers:{origin:"https://evil.invalid", "x-forwarded-host":"evil.invalid", "x-forwarded-proto":"https"}})), false);
  assert.equal(samePublicOrigin(new Request("https://alphapoker.io/test")), false);
  assert.equal(publicRequestUrl("http://alphapoker.io.evil.invalid/test").protocol, "http:");
});
