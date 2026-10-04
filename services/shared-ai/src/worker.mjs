// One persistent coordinator shares quotas across installations and Worker replicas.
// No prompts, responses, saves, raw IPs or provider keys are stored or logged.
const UPSTREAM = "https://api.groq.com/openai/v1/chat/completions";
const MODELS = new Set(["qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b"]);
const DAY = 86400000;
const encoder = new TextEncoder();
const json = (value, status = 200, headers = {}) => Response.json(value, {
  status, headers: { "Cache-Control": "no-store", ...headers },
});
class Refusal extends Error {
  constructor(code, status, retry = 0) { super(code); this.status = status; this.retry = retry; }
}
function refuse(code, status, retry = 0) { throw new Refusal(code, status, retry); }
function encoded(bytes) { return btoa(String.fromCharCode(...bytes)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", ""); }
function decoded(text) {
  return Uint8Array.from(atob(text.replaceAll("-", "+").replaceAll("_", "/")), c => c.charCodeAt(0));
}
async function readJSON(request, limit) {
  if (!request.headers.get("Content-Type")?.startsWith("application/json")) refuse("JSON_REQUIRED", 415);
  const reader = request.body?.getReader();
  if (!reader) refuse("INVALID_REQUEST", 400);
  const chunks = []; let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > limit) { await reader.cancel(); refuse("REQUEST_TOO_LARGE", 413); }
    chunks.push(value);
  }
  const result = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.byteLength; }
  try { return JSON.parse(new TextDecoder().decode(result)); }
  catch { refuse("INVALID_JSON", 400); }
}
function prompt(body, model) {
  const limits = { dialogue: 650, entity: 1500, search: 500 };
  if (!body || !Object.hasOwn(limits, body.purpose)
      || Object.keys(body).some(key => !["purpose", "messages"].includes(key))
      || !Array.isArray(body.messages) || body.messages.length !== 2) refuse("INVALID_REQUEST", 400);
  for (let i = 0; i < 2; i++) {
    const message = body.messages[i];
    if (!message || message.role !== ["system", "user"][i]
        || typeof message.content !== "string" || !message.content.trim()
        || Object.keys(message).some(key => !["role", "content"].includes(key))) refuse("INVALID_MESSAGES", 400);
  }
  const bytes = body.messages.reduce((sum, item) => sum + encoder.encode(item.content).length, 0);
  if (bytes > 18000) refuse("PROMPT_TOO_LARGE", 413);
  const isQwen = model.startsWith("qwen/");
  const output = isQwen ? { dialogue: 320, entity: 256, search: 64 }[body.purpose] : 768;
  return {
    maxCharacters: limits[body.purpose],
    // Conservative estimate, reconciled with usage after success; provider quotas
    // remain authoritative. Failed calls retain their reservation.
    reservation: Math.ceil(bytes / 3) + 256 + output,
    upstream: { model, messages: body.messages, stream: false,
      temperature: body.purpose === "search" ? 0 : 0.6, max_completion_tokens: output,
      ...(isQwen ? { reasoning_effort: "none", reasoning_format: "hidden" }
        : { reasoning_effort: "low", include_reasoning: false }),
    },
  };
}

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (path === "/health" && request.method === "GET") return json({ ready: Boolean(env.GROQ_API_KEY) });
    if (!["/v1/session", "/v1/chat/completions"].includes(path)) return json({ error: "NOT_FOUND" }, 404);
    if (request.method !== "POST") return json({ error: "METHOD_NOT_ALLOWED" }, 405);
    if (!env.GROQ_API_KEY) return json({ error: "AI_NOT_CONFIGURED" }, 503, { "Retry-After": "60" });
    const ip = request.headers.get("CF-Connecting-IP");
    if (!ip) return json({ error: "NETWORK_ID_UNAVAILABLE" }, 503);
    // CF-Connecting-IP is set by Cloudflare, never accept a client-selected ID.
    const forwarded = new Request(request);
    forwarded.headers.set("X-Lain-Network", ip);
    try {
      return await env.AI_BUDGET.get(env.AI_BUDGET.idFromName("shared-budget-v1")).fetch(forwarded);
    } catch {
      return json({ error: "AI_UNAVAILABLE" }, 503, { "Retry-After": "30" });
    }
  },
};

export class AIBudget {
  constructor(ctx, env) {
    this.ctx = ctx; this.env = env;
    this.ready = ctx.blockConcurrencyWhile(async () => {
      let secret = await ctx.storage.get("signing-key");
      if (!secret) {
        secret = Array.from(crypto.getRandomValues(new Uint8Array(32)));
        await ctx.storage.put("signing-key", secret);
      }
      this.key = await crypto.subtle.importKey("raw", new Uint8Array(secret),
        { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
    });
  }
  now() { return Date.now(); }
  upstream(request, options) { return fetch(request, options); }
  async signature(text) { return new Uint8Array(await crypto.subtle.sign("HMAC", this.key, encoder.encode(text))); }
  async mutate(change) {
    const now = this.now();
    return this.ctx.storage.transaction(async tx => {
      let state = await tx.get("quota");
      const day = Math.floor(now / DAY);
      if (!state || state.day !== day) {
        // Preserve the rolling window and active reservations across midnight.
        state = { day, issued: 0, issuedIPs: {}, calls: 0, tokens: 0, ips: {}, sessions: {},
          recent: state?.recent ?? [], cooldown: state?.cooldown ?? 0 };
      }
      state.recent = state.recent.filter(item => now - item.at < 60000);
      const result = change(state, now);
      await tx.put("quota", state);
      return result;
    });
  }
  async network(request) {
    const ip = request.headers.get("X-Lain-Network");
    if (!ip || ip.length > 64) refuse("NETWORK_ID_UNAVAILABLE", 503);
    // Rotate the digest daily; no raw address or persistent network history.
    return encoded(await this.signature(`ip:${Math.floor(this.now() / DAY)}:${ip}`));
  }
  async issue(ip) {
    await this.mutate((state, now) => {
      if (state.issued >= 100 || (state.issuedIPs[ip] ?? 0) >= 20) refuse("SESSION_LIMIT", 429, Math.ceil((DAY - now % DAY) / 1000));
      state.issued++; state.issuedIPs[ip] = (state.issuedIPs[ip] ?? 0) + 1;
    });
    const expires_at = Math.floor(this.now() / 1000) + 7 * 86400;
    const payload = encoded(encoder.encode(JSON.stringify({ id: crypto.randomUUID(), exp: expires_at })));
    return json({ token: payload + "." + encoded(await this.signature(payload)), expires_at });
  }
  async authorize(request) {
    const header = request.headers.get("Authorization");
    if (!header?.startsWith("Bearer ")) refuse("INVALID_SESSION", 401);
    const token = header.slice(7);
    if (!token || token.length > 2048) refuse("INVALID_SESSION", 401);
    try {
      const parts = token.split(".");
      if (parts.length !== 2 || !await crypto.subtle.verify("HMAC", this.key, decoded(parts[1]), encoder.encode(parts[0]))) throw new Error();
      const value = JSON.parse(new TextDecoder().decode(decoded(parts[0])));
      if (typeof value.id !== "string" || value.id.length !== 36 || !Number.isInteger(value.exp)
          || value.exp <= this.now() / 1000) throw new Error();
      return value.id;
    } catch { refuse("INVALID_SESSION", 401); }
  }
  async reserve(ip, session, tokens) {
    return this.mutate((state, now) => {
      if (state.cooldown > now) refuse("PROVIDER_COOLDOWN", 429, Math.ceil((state.cooldown - now) / 1000));
      if (state.calls >= 800 || state.tokens + tokens > 160000
          || (state.ips[ip] ?? 0) >= 300 || (state.sessions[session] ?? 0) >= 200) {
        refuse("DAILY_LIMIT", 429, Math.ceil((DAY - now % DAY) / 1000));
      }
      if (state.recent.length >= 24 || state.recent.filter(item => item.ip === ip).length >= 12
          || state.recent.filter(item => item.session === session).length >= 10
          || state.recent.reduce((sum, item) => sum + item.tokens, 0) + tokens > 7000) {
        refuse("MINUTE_LIMIT", 429, 60);
      }
      if (state.recent.filter(item => item.pending && now - item.at < 25000).length >= 2) refuse("AI_BUSY", 429, 3);
      const ticket = { id: crypto.randomUUID(), at: now, day: state.day, tokens, ip, session, pending: true };
      state.calls++; state.tokens += tokens;
      state.ips[ip] = (state.ips[ip] ?? 0) + 1;
      state.sessions[session] = (state.sessions[session] ?? 0) + 1;
      state.recent.push(ticket);
      return ticket;
    });
  }
  async settle(ticket, usage, retry = 0) {
    await this.mutate((state, now) => {
      const record = state.recent.find(item => item.id === ticket.id);
      if (record) {
        if (Number.isInteger(usage) && usage > 0 && usage < 100000) {
          if (ticket.day === state.day) state.tokens += usage - record.tokens;
          record.tokens = usage;
        }
        record.pending = false;
      }
      state.cooldown = Math.max(state.cooldown, now + retry * 1000);
    });
  }
  async chat(request, ip) {
    const session = await this.authorize(request);
    const body = await readJSON(request, 32768);
    const model = this.env.GROQ_MODEL || "qwen/qwen3.8-27b";
    if (!MODELS.has(model)) refuse("MODEL_NOT_CONFIGURED", 503, 60);
    const prepared = prompt(body, model);
    const ticket = await this.reserve(ip, session, prepared.reservation);
    let usage; let retry = 0;
    try {
      const response = await this.upstream(UPSTREAM, {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: "Bearer " + this.env.GROQ_API_KEY },
        body: JSON.stringify(prepared.upstream), redirect: "manual", signal: AbortSignal.timeout(20000),
      });
      if (!response.ok) {
        await response.body?.cancel();
        const parsed = Number(response.headers.get("Retry-After"));
        retry = response.status === 429 ? Math.max(1, Math.min(86400, Number.isFinite(parsed) && parsed > 0 ? parsed : 60)) : 30;
        refuse(response.status === 429 ? "PROVIDER_LIMIT" : "PROVIDER_UNAVAILABLE", response.status === 429 ? 429 : 503, retry);
      }
      const data = await readJSON(response, 65536);
      usage = data.usage?.total_tokens;
      const text = data.choices?.[0]?.message?.content;
      if (typeof text !== "string" || !text.trim() || text.length > prepared.maxCharacters
          || /[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(text)
          || data.choices[0].finish_reason === "length") refuse("INVALID_PROVIDER_RESPONSE", 502, 10);
      // Do not forward reasoning, upstream identifiers, headers or diagnostic bodies.
      return json({ choices: [{ message: { role: "assistant", content: text.trim() } }] });
    } catch (error) {
      if (error instanceof Refusal) throw error;
      retry = 30; refuse("PROVIDER_UNAVAILABLE", 503, retry);
    } finally { await this.settle(ticket, usage, retry); }
  }
  async fetch(request) {
    try {
      await this.ready;
      const ip = await this.network(request);
      if (new URL(request.url).pathname === "/v1/session") {
        const body = await readJSON(request, 256);
        if (!body || Array.isArray(body) || Object.keys(body).length) refuse("INVALID_REQUEST", 400);
        return await this.issue(ip);
      }
      return await this.chat(request, ip);
    } catch (error) {
      if (error instanceof Refusal) return json({ error: error.message }, error.status,
        error.retry ? { "Retry-After": String(error.retry) } : {});
      return json({ error: "AI_UNAVAILABLE" }, 503, { "Retry-After": "30" });
    }
  }
}
