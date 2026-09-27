import { test } from "node:test";
import assert from "node:assert/strict";
import worker, { AIBudget } from "../src/worker.mjs";

function storage() {
  const data = new Map(); let queue = Promise.resolve();
  const store = {
    async get(key) { return structuredClone(data.get(key)); },
    async put(key, value) { data.set(key, structuredClone(value)); },
    transaction(fn) {
      const operation = queue.then(async () => {
        const before = structuredClone(data);
        try { return await fn(store); }
        catch (error) { data.clear(); for (const [k, v] of before) data.set(k, v); throw error; }
      });
      queue = operation.catch(() => {}); return operation;
    },
  };
  return store;
}
async function setup() {
  const saved = storage();
  const env = { GROQ_API_KEY: "private-test-key", GROQ_MODEL: "qwen/qwen3.8-27b" };
  const ctx = { storage: saved, blockConcurrencyWhile: fn => fn() };
  const budget = new AIBudget(ctx, env);
  await budget.ready;
  budget.now = () => Date.UTC(2026, 8, 27, 12);
  let calls = 0;
  budget.upstream = async (url, options) => {
    calls++; assert.equal(url, "https://api.groq.com/openai/v1/chat/completions");
    assert.equal(options.headers.Authorization, "Bearer private-test-key");
    assert.equal(options.redirect, "manual");
    const body = JSON.parse(options.body);
    assert.equal(body.model, env.GROQ_MODEL); assert.equal(body.stream, false);
    return Response.json({ choices: [{ message: { content: "Hola.", reasoning: "private reasoning" }, finish_reason: "stop" }], usage: { total_tokens: 80 } });
  };
  const request = (path, body = {}, token = "", ip = "198.51.100.4") => new Request("https://lain.example" + path, {
    method: "POST", headers: { "Content-Type": "application/json", "X-Lain-Network": ip, Authorization: "Bearer " + token }, body: JSON.stringify(body),
  });
  const session = async ip => (await (await budget.fetch(request("/v1/session", {}, "", ip))).json()).token;
  const message = { purpose: "dialogue", messages: [{ role: "system", content: "Speak Spanish." }, { role: "user", content: "Hola" }] };
  const chat = (token, body = message, ip) => budget.fetch(request("/v1/chat/completions", body, token, ip));
  return { budget, ctx, env, saved, request, session, chat, message, calls: () => calls };
}

test("anonymous session, bounded reply, no stored prompts or raw IPs", async () => {
  const s = await setup(); const token = await s.session();
  const reply = await s.chat(token);
  assert.equal(reply.status, 200);
  assert.deepEqual(await reply.json(), { choices: [{ message: { role: "assistant", content: "Hola." } }] });
  const state = JSON.stringify(await s.saved.get("quota"));
  for (const secret of ["Hola", "198.51.100", "private-test-key", "Speak Spanish"]) assert.ok(!state.includes(secret));
  assert.equal((await s.saved.get("quota")).tokens, 80);
});
test("forged, missing and expired sessions never call Groq", async () => {
  const s = await setup(); const token = await s.session();
  assert.equal((await s.chat("")).status, 401);
  assert.equal((await s.chat(token + "tampered")).status, 401);
  s.budget.now = () => Date.UTC(2026, 9, 6);
  assert.equal((await s.chat(token)).status, 401); assert.equal(s.calls(), 0);
});
test("session issuance is capped per network and resets next UTC day", async () => {
  const s = await setup();
  for (let i = 0; i < 20; i++) assert.ok(await s.session());
  assert.equal((await s.budget.fetch(s.request("/v1/session"))).status, 429);
  s.budget.now = () => Date.UTC(2026, 8, 28);
  assert.ok(await s.session());
});
test("reject alternate endpoints, models, tools, oversized prompts and messages", async () => {
  const s = await setup(); const token = await s.session();
  for (const body of [{ ...s.message, model: "expensive" }, { ...s.message, tools: [] },
    { ...s.message, endpoint: "https://attacker.example" }, { ...s.message, purpose: "unknown" },
    { ...s.message, messages: [{ role: "user", content: "x" }] }]) assert.equal((await s.chat(token, body)).status, 400);
  assert.equal((await s.chat(token, { ...s.message, messages: [{ role: "system", content: "x".repeat(18001) }, s.message.messages[1]] })).status, 413);
  assert.equal(s.calls(), 0);
});
test("concurrent requests reserve capacity before upstream and release after", async () => {
  const s = await setup(); const token = await s.session(); let release;
  const pending = new Promise(resolve => { release = resolve; }); let entered = 0;
  s.budget.upstream = async () => { entered++; await pending; return Response.json({ choices: [{ message: { content: "Sí." } }] }); };
  const first = s.chat(token), second = s.chat(token);
  while (entered < 2) await new Promise(resolve => setImmediate(resolve));
  assert.equal((await s.chat(token)).status, 429);
  release(); assert.equal((await first).status, 200); assert.equal((await second).status, 200);
  assert.equal((await s.chat(token)).status, 200);
});
test("daily global budget persists across object recreation, despite new sessions", async () => {
  const s = await setup(); const token = await s.session(); await s.chat(token);
  const state = await s.saved.get("quota"); state.tokens = 159999; await s.saved.put("quota", state);
  const restarted = new AIBudget(s.ctx, s.env); await restarted.ready;
  restarted.now = s.budget.now;
  const response = await restarted.fetch(s.request("/v1/chat/completions", s.message, token));
  assert.equal(response.status, 429); assert.equal((await response.json()).error, "DAILY_LIMIT");
});
test("rolling token limit crosses midnight and later clears", async () => {
  const s = await setup(); const token = await s.session();
  s.budget.now = () => Date.UTC(2026, 8, 27, 23, 59, 59);
  await s.budget.reserve("network", "session", 6990);
  s.budget.now = () => Date.UTC(2026, 8, 28, 0, 0, 1);
  assert.equal((await s.chat(token)).status, 429);
  s.budget.now = () => Date.UTC(2026, 8, 28, 0, 1, 1);
  assert.equal((await s.chat(token)).status, 200);
});
test("upstream 429 is sanitized and puts all players on cooldown", async () => {
  const s = await setup(); const token = await s.session(); let calls = 0;
  s.budget.upstream = async () => { calls++; return new Response("secret diagnostics", { status: 429, headers: { "Retry-After": "120" } }); };
  const response = await s.chat(token);
  assert.equal(response.status, 429); assert.equal(response.headers.get("Retry-After"), "120");
  assert.ok(!(await response.text()).includes("secret"));
  assert.equal((await s.chat(await s.session("198.51.100.5"), s.message, "198.51.100.5")).status, 429);
  assert.equal(calls, 1);
});
test("failed and malformed responses retain reservation and release concurrency", async () => {
  const s = await setup(); const token = await s.session();
  s.budget.upstream = async () => Response.json({ choices: [{ message: { content: "x".repeat(651) } }] });
  assert.equal((await s.chat(token)).status, 502);
  const quota = await s.saved.get("quota"); assert.ok(quota.tokens > 0); assert.equal(quota.recent[0].pending, false);
});
test("gateway without owner's key fails closed and health uses no upstream", async () => {
  assert.equal((await worker.fetch(new Request("https://lain.example/v1/session", { method: "POST" }), {})).status, 503);
  assert.deepEqual(await (await worker.fetch(new Request("https://lain.example/health"), {})).json(), { ready: false });
  assert.equal((await worker.fetch(new Request("https://lain.example/unknown"), {})).status, 404);
});
