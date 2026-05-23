"use client";

import { useCallback, useState } from "react";
import ArticlePreview from "../components/ArticlePreview";
import Recorder from "../components/Recorder";
import type { ArticleResponse } from "../lib/api";

export default function Home() {
  const [article, setArticle] = useState<ArticleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const handleArticleReady = useCallback((data: ArticleResponse) => {
    setArticle(data);
    setError(null);
  }, []);

  const handleError = useCallback((msg: string) => {
    setError(msg);
  }, []);

  const handleReset = useCallback(() => {
    setArticle(null);
    setError(null);
    setIsProcessing(false);
  }, []);

  return (
    <main className="min-h-screen bg-zinc-950 text-white">
      {/* Nav */}
      <nav className="border-b border-zinc-800/60 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-rose-500 flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 1a4 4 0 0 1 4 4v7a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4zm0 2a2 2 0 0 0-2 2v7a2 2 0 0 0 4 0V5a2 2 0 0 0-2-2zm-7 9h2a5 5 0 0 0 10 0h2a7 7 0 0 1-6 6.93V21h4v2H7v-2h4v-2.07A7 7 0 0 1 5 12z" />
            </svg>
          </div>
          <span className="font-bold text-lg tracking-tight">VoiceNote</span>
        </div>
        <div className="text-xs text-zinc-500">Talk. Get a publish-ready article.</div>
      </nav>

      {/* Hero — shown only before recording completes */}
      {!article && (
        <section className="text-center px-6 pt-16 pb-10">
          <div className="inline-flex items-center gap-2 bg-zinc-800/80 border border-zinc-700/60 rounded-full px-4 py-1.5 text-xs text-zinc-400 mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Powered by Whisper + Claude
          </div>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight leading-tight mb-4 max-w-xl mx-auto">
            Talk for 5 minutes,<br />
            <span className="text-rose-400">get a polished article.</span>
          </h1>
          <p className="text-zinc-400 max-w-md mx-auto text-lg leading-relaxed mb-10">
            Founders, creators, and podcasters — stop fighting the blank page.
            Your ideas are already there. Just say them.
          </p>

          {/* How it works */}
          <div className="flex flex-wrap justify-center gap-4 mb-12">
            {[
              { step: "1", label: "Click Start", sub: "Mic permission → recording begins" },
              { step: "2", label: "Talk freely", sub: "2–5 min, any topic, no script needed" },
              { step: "3", label: "Get article", sub: "Whisper transcribes, Claude structures" },
            ].map(({ step, label, sub }) => (
              <div
                key={step}
                className="flex items-start gap-3 bg-zinc-800/40 border border-zinc-700/40 rounded-xl px-4 py-3 text-left max-w-[200px]"
              >
                <div className="w-6 h-6 rounded-full bg-rose-500/20 text-rose-400 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                  {step}
                </div>
                <div>
                  <div className="text-sm font-semibold text-white">{label}</div>
                  <div className="text-xs text-zinc-400 mt-0.5">{sub}</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Main content */}
      <div className="flex flex-col items-center px-6 pb-20">
        {/* Error banner */}
        {error && (
          <div className="w-full max-w-md mb-6 bg-red-950/60 border border-red-800/60 rounded-xl px-4 py-3 text-sm text-red-300">
            <span className="font-semibold">Error: </span>{error}
          </div>
        )}

        {/* Article preview (post-generation) */}
        {article ? (
          <ArticlePreview article={article} onReset={handleReset} />
        ) : (
          <Recorder
            onArticleReady={handleArticleReady}
            onError={handleError}
            isProcessing={isProcessing}
            setIsProcessing={setIsProcessing}
          />
        )}

        {/* VS comparison (only on landing) */}
        {!article && !isProcessing && (
          <div className="mt-16 w-full max-w-2xl">
            <p className="text-center text-xs text-zinc-600 mb-4 uppercase tracking-widest font-medium">
              How VoiceNote compares
            </p>
            <div className="overflow-x-auto rounded-xl border border-zinc-800">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800">
                    <th className="text-left px-4 py-3 text-zinc-500 font-medium">Feature</th>
                    <th className="px-4 py-3 text-zinc-400 font-medium">Otter/Whisper</th>
                    <th className="px-4 py-3 text-zinc-400 font-medium">Riverside/Descript</th>
                    <th className="px-4 py-3 text-rose-400 font-semibold">VoiceNote</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60">
                  {[
                    ["Live transcript", "Yes", "Yes", "No (batch)"],
                    ["Structured article", "No", "No", "Yes"],
                    ["1-click publish", "No", "No", "Yes (Substack)"],
                    ["Price", "$17/mo", "$24/mo", "~$0.04/article"],
                  ].map(([feature, otter, riverside, voicenote]) => (
                    <tr key={feature}>
                      <td className="px-4 py-3 text-zinc-400">{feature}</td>
                      <td className="px-4 py-3 text-center text-zinc-500">{otter}</td>
                      <td className="px-4 py-3 text-center text-zinc-500">{riverside}</td>
                      <td className="px-4 py-3 text-center text-rose-300 font-medium">{voicenote}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
