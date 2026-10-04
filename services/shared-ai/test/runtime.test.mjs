import { test } from "node:test";
import assert from "node:assert/strict";
import { Miniflare, convertV4MiniflareOptions } from "miniflare";
import { fileURLToPath } from "node:url";

test("real Worker runtime and SQLite Durable Object: session and dialogue", async () => {
  let calls = 0;
  let upstreamURL;
  let authorization;
  const mf = new Miniflare(convertV4MiniflareOptions({
    modules: true, scriptPath: fileURLToPath(new URL("../src/worker.mjs", import.meta.url)),
    compatibilityDate: "2026-09-27", durableObjects: { AI_BUDGET: { className: "AIBudget", useSQLite: true } },
    bindings: { GROQ_API_KEY: "test-key-never-a-real-secret", GROQ_MODEL: "qwen/qwen3.8-27b" },
    outboundService: async request => {
      calls++;
      upstreamURL = request.url;
      authorization = request.headers.get("Authorization");
      return Response.json({ choices: [{ message: { content: "Te escucho." }, finish_reason: "stop" }], usage: { total_tokens: 70 } });
    },
  }));
  try {
    const headers = { "Content-Type": "application/json", "CF-Connecting-IP": "198.51.100.10" };
    const response = await mf.dispatchFetch("https://lain.example/v1/session", { method: "POST", headers, body: "{}" });
    assert.equal(response.status, 200, await response.clone().text());
    const { token } = await response.json();
    const reply = await mf.dispatchFetch("https://lain.example/v1/chat/completions", {
      method: "POST", headers: { ...headers, Authorization: "Bearer " + token },
      body: JSON.stringify({ purpose: "dialogue", messages: [{ role: "system", content: "Habla en español." }, { role: "user", content: "Hola" }] }),
    });
    assert.equal(reply.status, 200, await reply.clone().text());
    assert.equal((await reply.json()).choices[0].message.content, "Te escucho.");
    assert.equal(calls, 1);
    assert.equal(upstreamURL, "https://api.groq.com/openai/v1/chat/completions");
    assert.equal(authorization, "Bearer test-key-never-a-real-secret");
  } finally { await mf.dispose(); }
});
