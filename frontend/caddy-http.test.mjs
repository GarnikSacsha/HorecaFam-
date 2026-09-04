import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { after, before, test } from "node:test";
import { setTimeout } from "node:timers/promises";
import { URL } from "node:url";

const image = "horeca-cra123-web-test";
const network = `horeca-caddy-test-${randomUUID()}`;
const containers = [];
let networkCreated = false;
let origin;
const docker = (...args) =>
  execFileSync("docker", args, { encoding: "utf8", timeout: 60_000 }).trim();
const request = (path, options = {}) =>
  globalThis.fetch(`${origin}${path}`, {
    ...options,
    signal: globalThis.AbortSignal.timeout(5_000),
  });

before(async () => {
  docker("image", "inspect", image);
  docker("image", "inspect", "node:24-alpine");
  docker("network", "create", network);
  networkCreated = true;
  containers.push(
    docker(
      "run",
      "--detach",
      "--network",
      network,
      "--network-alias",
      "upstream",
      "node:24-alpine",
      "node",
      "-e",
      'require("node:http").createServer((req,res)=>{res.setHeader("content-type","application/json");res.end(JSON.stringify({path:req.url,method:req.method}));}).listen(8000,"0.0.0.0")',
    ),
  );
  containers.push(
    docker(
      "run",
      "--detach",
      "--network",
      network,
      "--publish",
      "127.0.0.1::8080",
      "--env",
      "API_UPSTREAM=http://upstream:8000",
      image,
    ),
  );
  origin = `http://${docker("port", containers[1], "8080/tcp")}`;
  for (let attempt = 0; attempt < 40; attempt++) {
    try {
      const response = await request("/api/v1/health");
      if (response.ok && (await response.json()).path === "/api/v1/health") return;
    } catch {
      // Обидва процеси мають бути готові до перевірки контракту.
    }
    await setTimeout(250);
  }
  throw new Error("Fixture startup failed: web and synthetic upstream are not ready");
});

after(() => {
  const errors = [];
  for (const container of containers.reverse()) {
    try {
      docker("rm", "--force", container);
    } catch (error) {
      errors.push(error);
    }
  }
  if (networkCreated) {
    try {
      docker("network", "rm", network);
    } catch (error) {
      errors.push(error);
    }
  }
  assert.equal(errors.length, 0, "Disposable fixture cleanup failed");
});

test("actual image validates Caddy and runs without root", () => {
  assert.equal(
    docker("exec", containers[1], "cat", "/etc/caddy/Caddyfile").replaceAll("\r\n", "\n"),
    readFileSync(new URL("./Caddyfile", import.meta.url), "utf8")
      .replaceAll("\r\n", "\n")
      .trim(),
    "Rebuild the image after changing the Caddyfile",
  );
  assert.notEqual(docker("exec", containers[1], "id", "-u"), "0");
  docker(
    "exec",
    containers[1],
    "caddy",
    "validate",
    "--config",
    "/etc/caddy/Caddyfile",
    "--adapter",
    "caddyfile",
  );
});

test("web health is a dedicated non-cacheable response", async () => {
  const response = await request("/healthz");
  assert.equal(response.status, 200);
  assert.equal(await response.text(), "ok");
  assert.equal(response.headers.get("cache-control"), "no-store");
});

test("HTML and SPA deep links are never stored", async () => {
  for (const path of ["/", "/index.html", "/employee/learning"]) {
    const response = await request(path);
    assert.equal(response.status, 200, path);
    assert.match(response.headers.get("content-type"), /text\/html/);
    assert.equal(response.headers.get("cache-control"), "no-store", path);
    assert.match(await response.text(), /<div id="root">/);
  }
});

test("built hashed JS and CSS are immutable", async () => {
  const html = await (await request("/")).text();
  const paths = [...html.matchAll(/(?:src|href)="(\/assets\/[^" ]+\.(?:js|css))"/g)].map(
    (match) => match[1],
  );
  assert.ok(paths.some((path) => path.endsWith(".js")));
  assert.ok(paths.some((path) => path.endsWith(".css")));
  for (const path of paths) {
    const response = await request(path);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "public, max-age=31536000, immutable");
    assert.doesNotMatch(response.headers.get("content-type"), /text\/html/);
    await response.arrayBuffer();
  }
});

test("missing hashed assets are 404 rather than cached SPA HTML", async () => {
  const response = await request("/assets/missing-Abcd1234.js");
  assert.equal(response.status, 404);
  assert.doesNotMatch(response.headers.get("cache-control") ?? "", /immutable|max-age=31536000/);
  assert.doesNotMatch(await response.text(), /<div id="root">/);
});

test("asset error responses do not receive immutable caching", async () => {
  const html = await (await request("/")).text();
  const path = html.match(/src="(\/assets\/[^" ]+\.js)"/)[1];
  for (const options of [{ method: "POST" }, { headers: { Range: "bytes=999999999-" } }]) {
    const response = await request(path, options);
    assert.ok(response.status >= 400);
    assert.doesNotMatch(response.headers.get("cache-control") ?? "", /immutable/);
    await response.text();
  }
});

test("API v1 preserves method, path and query", async () => {
  for (const path of ["/api/v1", "/api/v1/health?check=1"]) {
    const response = await request(path, { method: "POST" });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { path, method: "POST" });
  }
});

test("unsupported API routes are rejected", async () => {
  for (const path of ["/api", "/api/internal", "/api/v10/health"]) {
    const response = await request(path);
    assert.equal(response.status, 404, path);
    assert.doesNotMatch(await response.text(), /<div id="root">/);
  }
});

test("security headers are retained", async () => {
  const response = await request("/");
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.equal(response.headers.get("referrer-policy"), "same-origin");
  assert.equal(response.headers.get("server"), null);
  await response.text();
});
