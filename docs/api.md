# API

The backend exposes two endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check. Returns `{"status":"ok"}`. Shallow: it does **not** verify PostgreSQL, Qdrant, DeepSeek, or the embedding model, and is not rate limited. |
| `POST` | `/query` | Answer a question from the indexed documentation and stream the response as NDJSON. |

## `POST /query`

Request body:

```json
{
  "query": "How do I create a FastAPI application?",
  "collection": "fastapi",
  "limit": 5
}
```

| Field | Type | Constraints | Default |
| --- | --- | --- | --- |
| `query` | string | 1–2000 characters | required |
| `collection` | string | 1–128 characters | required |
| `limit` | integer | 1–20 | `5` |

Field length limits are enforced by the request schema, so oversized values are
rejected before any collection lookup or generation.

### Streaming response

The response media type is `application/x-ndjson`: each line is a JSON object.
The stream begins with exactly one `sources` event, followed by zero or more
incremental `text` events, and ends with exactly one terminal event — `complete`
on success, or `error` on failure.

```json
{"type":"sources","sources":[{"source":"...","source_uri":"filesystem://path-params.md","chunk_index":17,"chunk_id":"...","score":0.863}]}
{"type":"text","text":"To create a FastAPI application, "}
{"type":"complete","retrieval_time_ms":24.8,"total_time_ms":1908.1}
```

On failure, the terminal event is:

```json
{"type":"error","code":"generation_failed","message":"..."}
```

Provider error details are never included in the response.

The `sources` event lists exactly the chunks included in the generation prompt,
in retrieval-rank order, so unused chunks are never presented as supporting
evidence.

### Status codes

| Condition | Response |
| --- | --- |
| Valid query | `200` streaming response |
| Empty query | `422` |
| Invalid `limit` | `422` |
| `query` exceeds 2000 characters | `422` |
| `collection` exceeds 128 characters | `422` |
| Missing required field | `422` |
| Malformed JSON | `422` |
| Nonexistent or disallowed collection | `404` |
| Rate limit exceeded | `429` (+ `Retry-After`) |

Collection existence is checked before the streaming response is created, so an
invalid collection cannot produce a broken stream.

### Collection allowlist

The public API serves only collections listed in `ALLOWED_COLLECTIONS`
(comma-separated, default `fastapi`). The allowlist is checked before any Qdrant
lookup, and disallowed and nonexistent collections return the **identical** `404`
message so the API does not reveal which collections exist
([ADR-005](adr/005-public-api-collection-allowlist.md)). An explicitly empty value
denies all collections.

### Cost bounds

The server bounds cost independently of the client:

- `MAX_OUTPUT_TOKENS` (default `1024`) caps the tokens generated per answer and is
  passed to DeepSeek as `max_output_tokens`.
- `MAX_CONTEXT_CHARACTERS` (default `12000`) caps the total chunk content included
  in the prompt. Whole chunks are added in retrieval-rank order until the budget
  is reached.

Both must be positive integers.

## Rate limiting

`POST /query` is rate limited per client — `RATE_LIMIT_REQUESTS` (default `10`)
requests per 60-second fixed window, enforced **before** collection lookup and
generation. Exceeding it returns `429` with a `Retry-After` header (whole seconds)
and a generic message. Rejected requests do not extend the window. `GET /health`
is not rate limited.

Client identity defaults to the direct TCP peer (`request.client.host`), which
cannot be spoofed through request headers.

The limiter is **best-effort abuse control, not a guaranteed spending cap**:

- State is in memory, per process. Each Cloud Run instance (and each Uvicorn
  worker) enforces its own counter, so the effective ceiling scales with the
  number of instances and no global limit is shared.
- Behind a proxy the direct peer is the proxy address, so all users share one
  bucket and the limit becomes effectively per instance rather than per end user.
- The window is fixed per client and anchored at the client's first request, so a
  burst of up to roughly twice the limit is possible across a window boundary.
- Tracked state is bounded and expired entries are pruned.

### Trusted forwarded client IP (Cloud Run)

Setting `RATE_LIMIT_TRUST_CLOUD_RUN_X_FORWARDED_FOR=true` makes the limiter read
the client IP from the trusted suffix of the `X-Forwarded-For` chain instead of
the direct peer. **Enable this only for verified direct Cloud Run ingress.** When
enabled, the last entry in the chain is used (the proxy appends the real client
IP); earlier, client-supplied entries are ignored, and the candidate must parse as
an IP address or the limiter falls back to the direct peer. Do not enable it for
an unverified or multi-hop proxy/CDN topology, where trusting the chain could
allow spoofing.

## Cross-origin requests (CORS)

`CORS_ALLOWED_ORIGINS` lists the browser origins allowed to call the API from a
different origin. Each entry must be an **exact** origin in the form
`scheme://host[:port]` — no path and no trailing slash. There is no wildcard,
substring, or regex matching, and `*` is rejected as a configuration error. An
empty value (the local default) disables CORS; local development uses the Vite
proxy and is same-origin.

CORS is **not authentication** and does not replace the API's abuse controls.
It is enforced by the browser, not the server.

See [`configuration.md`](configuration.md) for the full set of settings.
