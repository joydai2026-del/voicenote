"use client";

import { useCallback, useState } from "react";
import ReactMarkdown from "react-markdown";
import type { ArticleResponse } from "../lib/api";

interface ArticlePreviewProps {
  article: ArticleResponse;
  onReset: () => void;
}

export default function ArticlePreview({ article, onReset }: ArticlePreviewProps) {
  const [copied, setCopied] = useState(false);
  const [transcriptOpen, setTranscriptOpen] = useState(false);

  const handleCopy = useCallback(async () => {
    const fullMarkdown = `# ${article.title}\n\n${article.body_md}`;
    try {
      await navigator.clipboard.writeText(fullMarkdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select all
      const el = document.createElement("textarea");
      el.value = fullMarkdown;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [article]);

  const handleDownload = useCallback(() => {
    const fullMarkdown = `# ${article.title}\n\n${article.body_md}`;
    const blob = new Blob([fullMarkdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    // Generate filename from title: lowercase, spaces to hyphens, strip special chars
    const slug = article.title
      .toLowerCase()
      .replace(/[^a-z0-9一-鿿\s-]/g, "")
      .replace(/\s+/g, "-")
      .slice(0, 60);
    a.download = `${slug || "article"}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [article]);

  const handleSubstack = useCallback(() => {
    // Substack URL-stuffing: opens new draft with title pre-filled.
    // Body via URL params is limited (~2KB), so we just open the compose page.
    const title = encodeURIComponent(article.title);
    const url = `https://substack.com/publish/post/new?title=${title}`;
    window.open(url, "_blank", "noopener,noreferrer");
  }, [article]);

  const wordCount = article.body_md.split(/\s+/).filter(Boolean).length;

  return (
    <div className="w-full max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-xs text-zinc-500 mb-3">
          <span className="bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full font-medium">
            Article ready
          </span>
          <span>{wordCount} words</span>
          <span>·</span>
          <span>${article.cost_usd.toFixed(3)} cost</span>
          {article.id !== "unsaved" && (
            <>
              <span>·</span>
              <span className="font-mono text-xs">id: {article.id.slice(0, 8)}</span>
            </>
          )}
        </div>

        <h1 className="text-2xl font-bold text-white leading-tight">
          {article.title}
        </h1>
      </div>

      {/* Sections overview */}
      {article.sections.length > 0 && (
        <div className="grid grid-cols-1 gap-2 mb-6">
          {article.sections.map((section, i) => (
            <div
              key={i}
              className="flex gap-3 p-3 bg-zinc-800/60 rounded-lg border border-zinc-700/50"
            >
              <div className="w-5 h-5 rounded-full bg-rose-500/20 text-rose-400 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                {i + 1}
              </div>
              <div>
                <div className="text-sm font-semibold text-white">{section.h2}</div>
                <div className="text-xs text-zinc-400 mt-0.5">{section.summary}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Article body */}
      <div className="prose prose-invert prose-sm max-w-none bg-zinc-800/40 rounded-xl p-5 border border-zinc-700/50 mb-4">
        <ReactMarkdown
          components={{
            h1: ({ children }) => (
              <h1 className="text-xl font-bold text-white mt-0 mb-3">{children}</h1>
            ),
            h2: ({ children }) => (
              <h2 className="text-lg font-semibold text-white mt-4 mb-2">{children}</h2>
            ),
            p: ({ children }) => (
              <p className="text-zinc-300 leading-relaxed mb-3">{children}</p>
            ),
            strong: ({ children }) => (
              <strong className="text-white font-semibold">{children}</strong>
            ),
          }}
        >
          {article.body_md}
        </ReactMarkdown>
      </div>

      {/* Action buttons */}
      <div className="flex flex-wrap gap-3 mb-4">
        <button
          onClick={handleCopy}
          className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-white text-zinc-900 font-semibold text-sm hover:bg-zinc-100 active:scale-95 transition-all shadow-lg"
        >
          {copied ? (
            <>
              <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Copied!
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              Copy Markdown
            </>
          )}
        </button>

        <button
          onClick={handleDownload}
          className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-zinc-700 text-white font-semibold text-sm hover:bg-zinc-600 active:scale-95 transition-all"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Download .md
        </button>

        <button
          onClick={handleSubstack}
          className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-orange-500/20 text-orange-300 font-semibold text-sm hover:bg-orange-500/30 active:scale-95 transition-all border border-orange-500/30"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M22.539 8.242H1.46V5.406h21.08v2.836zM1.46 10.812V24L12 18.11 22.54 24V10.812H1.46zM22.54 0H1.46v2.836h21.08V0z"/>
          </svg>
          Publish to Substack
        </button>

        <button
          onClick={onReset}
          className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-transparent text-zinc-500 font-semibold text-sm hover:text-zinc-300 active:scale-95 transition-all border border-zinc-700"
        >
          Try Again
        </button>
      </div>

      {/* Raw transcript collapsible */}
      <div className="border border-zinc-700/50 rounded-xl overflow-hidden">
        <button
          onClick={() => setTranscriptOpen((v) => !v)}
          className="w-full flex items-center justify-between px-4 py-3 text-sm text-zinc-400 hover:text-zinc-300 hover:bg-zinc-800/40 transition-all"
        >
          <span className="font-medium">Raw transcript</span>
          <svg
            className={`w-4 h-4 transition-transform duration-200 ${transcriptOpen ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {transcriptOpen && (
          <div className="px-4 pb-4 bg-zinc-900/40">
            <p className="text-xs text-zinc-500 leading-relaxed whitespace-pre-wrap font-mono">
              {article.transcript}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
