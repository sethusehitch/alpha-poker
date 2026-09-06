import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync, statSync } from "node:fs";
import test from "node:test";

const text = (path) => readFileSync(path, "utf8");

test("compose exposes only Caddy and persists application data", () => {
  const compose = text("compose.yaml");
  const caddyImage = text("Dockerfile.caddy");

  assert.match(compose, /ALPHA_POKER_PORT:-8080}:8080/);
  assert.match(compose, /alpha_poker_data:\/data/);
  assert.match(compose, /DATABASE_URL: sqlite:\/\/\/\/data\/alpha-poker\.sqlite3/);
  assert.match(compose, /MATCH_CONCURRENCY:-1/);
  assert.match(
    compose,
    /ALPHA_POKER_API_URL: http:\/\/api:8000\/v1/,
    "the web container's server-side auth proxy must reach the API service",
  );
  assert.match(compose, /ALPHA_POKER_AUTH_REQUIRED:-true/);
  assert.match(compose, /ALPHA_POKER_RETAINED_ARTIFACT_RUNS:-30/);
  assert.match(compose, /dockerfile: Dockerfile\.caddy/);
  assert.doesNotMatch(compose, /\.\/Caddyfile:\/etc\/caddy\/Caddyfile/);
  assert.match(caddyImage, /COPY \$\{CADDYFILE\} \/etc\/caddy\/Caddyfile/);

  const publishedPorts = [...compose.matchAll(/^\s{4}ports:\s*$/gm)];
  assert.equal(publishedPorts.length, 1, "only Caddy should publish a host port");
});

test("Caddy sends API and training WebSocket traffic to FastAPI", () => {
  const caddy = text("Caddyfile");

  assert.match(caddy, /handle_path \/api\/\*/);
  assert.match(caddy, /handle \/v1\/\*/);
  assert.match(caddy, /handle \/docs\*/);
  assert.match(caddy, /handle \/openapi\.json/);
  assert.match(caddy, /reverse_proxy api:8000/);
  assert.match(caddy, /reverse_proxy web:3000/);
  assert.doesNotMatch(caddy, /handle \/browser-api\/\*/);
  assert.match(caddy, /Content-Security-Policy/);
  assert.match(caddy, /script-src[^\n]+https:\/\/cdn\.jsdelivr\.net/);
  assert.match(caddy, /X-Frame-Options "DENY"/);
  const smoke = text("ops/smoke.sh");
  const websocketSmoke = text("ops/smoke-websocket.mjs");
  assert.match(smoke, /\/openapi\.json/);
  assert.match(websocketSmoke, /\/v1\/account\/status/);
});

test("AWS hosting keeps the fallback URL while serving the Route 53 domain", () => {
  const caddy = text("Caddyfile.aws");
  const compose = text("compose.aws.yaml");
  const terraform = text("infra/aws/lightsail/main.tf");

  assert.match(caddy, /ALPHA_POKER_PRIMARY_HOSTNAME/);
  assert.match(caddy, /ALPHA_POKER_WWW_HOSTNAME/);
  assert.match(caddy, /ALPHA_POKER_TEMPORARY_HOSTNAME/);
  assert.match(compose, /ALPHA_POKER_PRIMARY_HOSTNAME/);
  assert.match(terraform, /resource "aws_route53_record" "app"/);
  assert.match(terraform, /resource "aws_route53_record" "www"/);
});

test("operations scripts are executable and valid POSIX shell", () => {
  const scripts = [
    "ops/start-api.sh",
    "ops/up.sh",
    "ops/down.sh",
    "ops/smoke.sh",
  ];

  for (const script of scripts) {
    assert.ok(statSync(script).mode & 0o100, `${script} must be executable`);
    execFileSync("sh", ["-n", script]);
  }

  const deploy = "ops/aws/deploy.sh";
  assert.ok(statSync(deploy).mode & 0o100, `${deploy} must be executable`);
  execFileSync("bash", ["-n", deploy]);
  const deploySource = text(deploy);
  assert.match(deploySource, /source\.backup\(target\)/);
  assert.match(deploySource, /-f "\$app_root\/current\/compose\.aws\.yaml"/);
  assert.doesNotMatch(deploySource, /cd "\$app_root\/current"\n\s*if docker compose/);
  assert.match(deploySource, /pre-deploy-\*\.sqlite3/);
  assert.match(deploySource, /backups\[10:\]/);
  const embeddedPython = deploySource.match(/api python -c '([\s\S]*?)'\n/);
  assert.ok(embeddedPython, "deploy script must contain the SQLite backup program");
  execFileSync("python3", ["-c", `compile(${JSON.stringify(embeddedPython[1])}, "<deploy-backup>", "exec")`]);
});
