/**
 * VoiceNote API client.
 *
 * Points at NEXT_PUBLIC_BACKEND_URL (set in Vercel env or .env.local).
 * Falls back to localhost:8000 for local development.
 */

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export interface ArticleSection {
  h2: string;
  summary: string;
}

export interface ArticleResponse {
  id: string;
  title: string;
  body_md: string;
  sections: ArticleSection[];
  transcript: string;
  cost_usd: number;
}

export async function generateArticle(
  audioBlob: Blob,
  filename?: string
): Promise<ArticleResponse> {
  const formData = new FormData();
  const file = new File([audioBlob], filename || "recording.webm", {
    type: audioBlob.type || "audio/webm",
  });
  formData.append("audio", file);

  const response = await fetch(`${BACKEND_URL}/articles/generate`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorBody = await response.text().catch(() => "Unknown error");
    let detail = errorBody;
    try {
      const json = JSON.parse(errorBody);
      detail = json.detail || json.message || errorBody;
    } catch {
      // use raw text
    }
    throw new Error(`Article generation failed (${response.status}): ${detail}`);
  }

  return response.json() as Promise<ArticleResponse>;
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${BACKEND_URL}/healthz`, {
      method: "GET",
      signal: AbortSignal.timeout(5000),
    });
    return response.ok;
  } catch {
    return false;
  }
}
