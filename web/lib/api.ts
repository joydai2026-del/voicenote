/**
 * VoiceNote frontend API client.
 *
 * The browser only ever talks to its own origin at /api/articles/generate.
 * That route is a Next.js server function (web/app/api/articles/generate/route.ts)
 * which holds the backend URL + API key via server-only env vars. Nothing
 * secret ships in the browser bundle.
 */

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

  const response = await fetch("/api/articles/generate", {
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
