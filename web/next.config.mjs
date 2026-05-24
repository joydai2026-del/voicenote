/** @type {import('next').NextConfig} */
const nextConfig = {
  // VOICENOTE_BACKEND_URL + VOICENOTE_API_KEY are server-only env vars
  // (no NEXT_PUBLIC_ prefix). They are read by web/app/api/articles/generate
  // at request time and never reach the browser bundle.
};

export default nextConfig;
