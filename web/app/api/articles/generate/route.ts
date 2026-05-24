/**
 * Server-side proxy for POST /articles/generate.
 *
 * The backend URL + API key are server-only env vars; the browser uploads
 * audio to this same-origin endpoint and never sees the backend secrets.
 *
 * Server env (no NEXT_PUBLIC_ prefix):
 *   VOICENOTE_BACKEND_URL   e.g. https://<...>.modal.run
 *   VOICENOTE_API_KEY       same value as the backend's VOICENOTE_API_KEY
 *
 * IMPORTANT: Vercel Hobby caps serverless POST bodies at 4.5 MB. We enforce
 * a tighter 4 MB cap here. Users wanting longer recordings need either
 * Vercel Pro (configurable up to 50 MB) or to hit the Modal backend directly
 * with the API key (advanced; documented in README).
 */

import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.VOICENOTE_BACKEND_URL || "http://localhost:8000";
const API_KEY = process.env.VOICENOTE_API_KEY || "";

const MAX_PROXY_BODY_BYTES = parseInt(
  process.env.MAX_PROXY_BODY_BYTES || `${4 * 1024 * 1024}`,
  10
);

const RATE_LIMIT_PER_HOUR = parseInt(
  process.env.PROXY_RATE_LIMIT_PER_HOUR || "5",
  10
);
const MAX_RATE_LIMIT_BUCKETS = 5_000;

const rateBuckets = new Map<string, number[]>();

function clientIp(req: Request): string {
  // Only platform-trusted headers; never the inbound x-forwarded-for (browser-controlled).
  const vercel = req.headers.get("x-vercel-forwarded-for");
  if (vercel) return vercel.split(",")[0].trim() || "unknown";
  const real = req.headers.get("x-real-ip");
  if (real) return real.trim() || "unknown";
  return "unknown";
}

function enforceRateLimit(ip: string): boolean {
  const now = Date.now();
  const windowStart = now - 3600 * 1000;
  const bucket = rateBuckets.get(ip) || [];
  const recent = bucket.filter((t) => t > windowStart);
  if (recent.length >= RATE_LIMIT_PER_HOUR) {
    rateBuckets.set(ip, recent);
    return false;
  }
  recent.push(now);
  rateBuckets.set(ip, recent);
  if (rateBuckets.size > MAX_RATE_LIMIT_BUCKETS) {
    const first = rateBuckets.keys().next().value;
    if (first !== undefined) rateBuckets.delete(first);
  }
  return true;
}

export async function POST(req: Request) {
  if (!API_KEY) {
    return NextResponse.json(
      { detail: "VOICENOTE_API_KEY is not configured on the Next.js server." },
      { status: 503 }
    );
  }

  const ip = clientIp(req);
  if (!enforceRateLimit(ip)) {
    return NextResponse.json(
      { detail: `Rate limit exceeded: ${RATE_LIMIT_PER_HOUR}/hour per IP.` },
      { status: 429 }
    );
  }

  const declared = parseInt(req.headers.get("content-length") || "0", 10);
  if (declared && declared > MAX_PROXY_BODY_BYTES) {
    return NextResponse.json(
      {
        detail: `Audio too large (${Math.round(declared / 1024)} KB > ${Math.round(MAX_PROXY_BODY_BYTES / 1024)} KB cap).`,
      },
      { status: 413 }
    );
  }

  // Read the multipart body as raw bytes with a streaming byte cap so a missing
  // or lying content-length cannot make us buffer unbounded data.
  if (!req.body) {
    return NextResponse.json({ detail: "Missing request body" }, { status: 400 });
  }
  const reader = req.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (!value) continue;
      total += value.byteLength;
      if (total > MAX_PROXY_BODY_BYTES) {
        try {
          await reader.cancel();
        } catch {
          /* best-effort */
        }
        return NextResponse.json(
          { detail: "Audio too large." },
          { status: 413 }
        );
      }
      chunks.push(value);
    }
  } catch {
    try {
      await reader.cancel();
    } catch {
      /* ignore */
    }
    return NextResponse.json({ detail: "Failed to read request body." }, { status: 400 });
  }

  const buffer = new Uint8Array(total);
  let offset = 0;
  for (const c of chunks) {
    buffer.set(c, offset);
    offset += c.byteLength;
  }

  const upstream = await fetch(`${BACKEND_URL}/articles/generate`, {
    method: "POST",
    headers: {
      "Content-Type": req.headers.get("content-type") || "application/octet-stream",
      "X-API-Key": API_KEY,
      "X-Forwarded-For": ip,
    },
    body: buffer,
  });

  const text = await upstream.text();
  return new NextResponse(text, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") || "application/json",
    },
  });
}
