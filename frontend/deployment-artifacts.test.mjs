import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import assert from "node:assert/strict";

function projectFile(name) {
  return readFileSync(resolve(import.meta.dirname, name), "utf-8");
}

test("Caddy serves the SPA and proxies same-origin API requests", () => {
  const caddyfile = projectFile("Caddyfile");

  assert.match(caddyfile, /@api path \/api\/v1 \/api\/v1\/\*/);
  assert.match(caddyfile, /reverse_proxy \{\$API_UPSTREAM:http:\/\/api\.railway\.internal:8000\}/);
  assert.match(caddyfile, /try_files \{path\} \/index\.html/);
  assert.match(caddyfile, /file_server/);
});

test("the web image runs as an unprivileged user", () => {
  const dockerfile = projectFile("Dockerfile");

  assert.match(dockerfile, /FROM node:24-alpine AS build/);
  assert.match(dockerfile, /USER caddy/);
  assert.match(dockerfile, /EXPOSE 8080/);
});
