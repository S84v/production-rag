import { afterEach, describe, expect, it, vi } from "vitest";
import { streamQuery, type QueryEvent, type QueryRequest } from "./api";

const REQUEST: QueryRequest = {
  query: "How does dependency injection work?",
  collection: "fastapi",
  limit: 5,
};

function ndjsonBody(...chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });

  return { ok: true, body: stream } as unknown as Response;
}

async function collect(response: Response): Promise<QueryEvent[]> {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
  const events: QueryEvent[] = [];

  await streamQuery(REQUEST, {
    onEvent: (event) => events.push(event),
  });

  return events;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("streamQuery", () => {
  it("sends the documented request payload to /query", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      ndjsonBody('{"type":"complete","retrieval_time_ms":1,"total_time_ms":2}\n'),
    );
    vi.stubGlobal("fetch", fetchMock);

    await streamQuery(REQUEST, { onEvent: () => {} });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/query");
    expect(init).toMatchObject({ method: "POST" });
    expect(JSON.parse(String(init.body))).toEqual({
      query: "How does dependency injection work?",
      collection: "fastapi",
      limit: 5,
    });
  });

  it("reassembles events split across chunk boundaries", async () => {
    const events = await collect(
      ndjsonBody(
        '{"type":"sources","sources":[{"source":"fi',
        'lesystem://body.md","source_uri":"filesystem://body.md","chunk_index":8,',
        '"chunk_id":"abc","score":0.85}]}\n',
        '{"type":"text","text":"Hello"}\n{"type":"text","text":" world"}\n',
        '{"type":"complete","retrieval_time_ms":12.5,"total_time_ms":99}\n',
      ),
    );

    expect(events.map((event) => event.type)).toEqual([
      "sources",
      "text",
      "text",
      "complete",
    ]);
    expect(events[0]).toMatchObject({ type: "sources" });
    expect(events[2]).toMatchObject({ type: "text", text: " world" });
    expect(events[3]).toMatchObject({
      type: "complete",
      retrieval_time_ms: 12.5,
      total_time_ms: 99,
    });
  });

  it("surfaces a terminal error event without throwing", async () => {
    const events = await collect(
      ndjsonBody(
        '{"type":"error","code":"generation_failed","message":"upstream failed"}\n',
      ),
    );

    expect(events).toEqual([
      { type: "error", code: "generation_failed", message: "upstream failed" },
    ]);
  });

  it("treats a stream without a terminal event as a failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(ndjsonBody('{"type":"text","text":"partial"}\n')),
    );

    await expect(
      streamQuery(REQUEST, { onEvent: () => {} }),
    ).rejects.toThrow("The answer stream ended unexpectedly.");
  });

  it("reports the server detail for non-OK responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 429,
        json: async () => ({ detail: "Too many requests" }),
      } as unknown as Response),
    );

    await expect(
      streamQuery(REQUEST, { onEvent: () => {} }),
    ).rejects.toThrow("Too many requests");
  });
});
