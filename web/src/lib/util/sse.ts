/**
 * Server-Sent Events (SSE) yordamchilari.
 * Streaming javoblarni brauzerga uzatish uchun.
 */

import type { StreamEvent } from "../types";

/** Hodisalar generatorini SSE javobiga aylantiradi. */
export function sseResponse(
  events: AsyncGenerator<StreamEvent, void, unknown>,
): Response {
  const encoder = new TextEncoder();

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      try {
        for await (const event of events) {
          controller.enqueue(encoder.encode(formatEvent(event)));
        }
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Nomaʼlum xatolik yuz berdi.";
        controller.enqueue(
          encoder.encode(formatEvent({ type: "error", message })),
        );
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
      // Nginx kabi proksilar buferlashini o'chiradi.
      "x-accel-buffering": "no",
    },
  });
}

function formatEvent(event: StreamEvent): string {
  return `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`;
}

/** Brauzer tomonda SSE oqimini o'qish. */
export async function* readSse(
  response: Response,
): AsyncGenerator<StreamEvent, void, unknown> {
  if (!response.body) throw new Error("Javobda oqim yoʻq.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";

    for (const block of blocks) {
      const dataLine = block
        .split("\n")
        .find((l) => l.startsWith("data: "));
      if (!dataLine) continue;
      try {
        yield JSON.parse(dataLine.slice(6)) as StreamEvent;
      } catch {
        // Buzilgan bo'lakni tashlab ketamiz.
      }
    }
  }
}

/** JSON xato javobi. */
export function errorJson(message: string, status = 400): Response {
  return Response.json({ error: message }, { status });
}
