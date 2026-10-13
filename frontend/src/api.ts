export type Source = {
    source: string;
    source_uri: string;
    chunk_index: number;
    chunk_id: string;
    score: number;
};

export type SourcesEvent = {
    type: "sources";
    sources: Source[];
};

export type TextEvent = {
    type: "text";
    text: string;
};

export type CompleteEvent = {
    type: "complete";
    retrieval_time_ms: number;
    total_time_ms: number;
};

export type ErrorEvent = {
    type: "error";
    code: string;
    message: string;
};

export type QueryEvent = SourcesEvent | TextEvent | CompleteEvent | ErrorEvent;

export type QueryRequest = {
    query: string;
    collection: string;
    limit: number;
};

type QueryCallbacks = {
    onEvent: (event: QueryEvent) => void;
};

export async function streamQuery(
    request: QueryRequest,
    callbacks: QueryCallbacks,
): Promise<void> {
    const response = await fetch("/query", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        let detail = `Request failed with status ${response.status}`;

        try {
            const body = (await response.json()) as { detail?: string };
            if (body.detail) {
                detail = body.detail;
            }
        } catch {
            // Keep the default error message.
        }

        throw new Error(detail);
    }

    if (!response.body) {
        throw new Error("Response body is not available.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let completed = false;

    const handleEvent = (event: QueryEvent): void => {
        if (event.type === "complete" || event.type === "error") {
            completed = true;
        }

        callbacks.onEvent(event);
    };

    try {
        while (true) {
            const { done, value } = await reader.read();

            if (done) {
                buffer += decoder.decode();

                const finalEvent = parseLine(buffer);
                if (finalEvent) {
                    handleEvent(finalEvent);
                }

                break;
            }

            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split("\n");
            buffer = lines.pop() ?? "";

            for (const line of lines) {
                const event = parseLine(line);
                if (event) {
                    handleEvent(event);
                }
            }
        }

        if (!completed) {
            throw new Error("The answer stream ended unexpectedly.");
        }
    } finally {
        reader.releaseLock();
    }
}

function parseLine(line: string): QueryEvent | null {
    const trimmed = line.trim();

    if (!trimmed) {
        return null;
    }

    return JSON.parse(trimmed) as QueryEvent;
}
