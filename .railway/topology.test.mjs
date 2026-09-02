import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import assert from "node:assert/strict";

const definition = readFileSync(resolve(import.meta.dirname, "railway.ts"), "utf-8");

test("topology declares the database and three bounded services", () => {
  assert.match(definition, /postgres\("postgres"\)/);
  assert.match(definition, /service\("api"/);
  assert.match(definition, /service\("worker"/);
  assert.match(definition, /service\("web"/);
  assert.match(definition, /healthcheck: "\/api\/v1\/health"/);
});

test("topology selects monorepo Dockerfiles and the worker entrypoint", () => {
  assert.equal((definition.match(/root: "backend"/g) ?? []).length, 2);
  assert.match(definition, /root: "frontend"/);
  assert.match(definition, /PORT: "8000"/);
  assert.match(definition, /start: "python -m app\.worker"/);
});

test("topology preserves external secrets without embedding values", () => {
  for (const name of [
    "MFA_ENCRYPTION_KEYS",
    "AUTH_THROTTLE_HMAC_KEY",
    "INVITATION_TOKEN_HMAC_KEYS",
    "PASSWORD_RESET_TOKEN_HMAC_KEYS",
    "RESEND_API_KEY",
  ]) {
    assert.match(definition, new RegExp(`${name}: preserve\\(\\)`));
  }
  assert.doesNotMatch(definition, /railway config apply/);
});
