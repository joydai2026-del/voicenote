"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type RecorderState = "idle" | "recording" | "processing" | "done" | "error";

interface RecorderProps {
  onArticleReady: (data: import("../lib/api").ArticleResponse) => void;
  onError: (msg: string) => void;
  isProcessing: boolean;
  setIsProcessing: (v: boolean) => void;
}

const MAX_DURATION_SECONDS = 300; // 5 minutes
const MIN_DURATION_SECONDS = 10; // enable Stop button after 10s

export default function Recorder({
  onArticleReady,
  onError,
  isProcessing,
  setIsProcessing,
}: RecorderProps) {
  const [state, setState] = useState<RecorderState>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [audioLevel, setAudioLevel] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number>(0);
  const streamRef = useRef<MediaStream | null>(null);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
      .toString()
      .padStart(2, "0");
    const s = (seconds % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  const stopAudioMonitor = useCallback(() => {
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    setAudioLevel(0);
  }, []);

  const startAudioMonitor = useCallback((stream: MediaStream) => {
    try {
      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const tick = () => {
        const data = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(data);
        const avg = data.reduce((a, b) => a + b, 0) / data.length;
        setAudioLevel(Math.min(100, avg * 2));
        animFrameRef.current = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      // AudioContext not available (e.g. SSR), silent fail
    }
  }, []);

  const handleStart = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/mp4";

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.start(1000); // collect chunks every 1s
      startTimeRef.current = Date.now();
      setState("recording");
      startAudioMonitor(stream);

      // Timer
      timerRef.current = setInterval(() => {
        const secs = Math.floor((Date.now() - startTimeRef.current) / 1000);
        setElapsed(secs);
        // Auto-stop at 5 minutes
        if (secs >= MAX_DURATION_SECONDS) {
          handleStop();
        }
      }, 500);
    } catch (err) {
      onError(
        err instanceof Error
          ? `Microphone access denied: ${err.message}`
          : "Could not access microphone. Please allow mic permission and try again."
      );
    }
  }, [onError, startAudioMonitor]);

  const handleStop = useCallback(async () => {
    if (!mediaRecorderRef.current) return;

    // Clear timer and audio monitor
    if (timerRef.current) clearInterval(timerRef.current);
    stopAudioMonitor();

    setState("processing");
    setIsProcessing(true);

    const recorder = mediaRecorderRef.current;

    // Collect remaining data and stop
    await new Promise<void>((resolve) => {
      recorder.onstop = () => resolve();
      recorder.stop();
    });

    // Stop mic
    streamRef.current?.getTracks().forEach((t) => t.stop());

    const audioBlob = new Blob(chunksRef.current, {
      type: recorder.mimeType || "audio/webm",
    });

    try {
      const { generateArticle } = await import("../lib/api");
      const article = await generateArticle(audioBlob);
      onArticleReady(article);
      setState("done");
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Article generation failed.";
      onError(msg);
      setState("error");
    } finally {
      setIsProcessing(false);
    }
  }, [onArticleReady, onError, setIsProcessing, stopAudioMonitor]);

  const handleReset = useCallback(() => {
    setState("idle");
    setElapsed(0);
    chunksRef.current = [];
    mediaRecorderRef.current = null;
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      stopAudioMonitor();
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [stopAudioMonitor]);

  const canStop = elapsed >= MIN_DURATION_SECONDS;
  const pct = Math.min(100, (elapsed / MAX_DURATION_SECONDS) * 100);

  return (
    <div className="flex flex-col items-center gap-6 w-full max-w-md">
      {/* Main button */}
      {state === "idle" && (
        <button
          onClick={handleStart}
          className="relative w-36 h-36 rounded-full bg-rose-500 hover:bg-rose-600 active:scale-95 transition-all shadow-2xl shadow-rose-500/40 flex items-center justify-center"
          aria-label="Start recording"
        >
          <svg
            className="w-14 h-14 text-white"
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M12 1a4 4 0 0 1 4 4v7a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4zm0 2a2 2 0 0 0-2 2v7a2 2 0 0 0 4 0V5a2 2 0 0 0-2-2zm-7 9h2a5 5 0 0 0 10 0h2a7 7 0 0 1-6 6.93V21h4v2H7v-2h4v-2.07A7 7 0 0 1 5 12z" />
          </svg>
        </button>
      )}

      {/* Recording state */}
      {state === "recording" && (
        <>
          {/* Pulsing ring + waveform */}
          <div className="relative flex items-center justify-center">
            {/* Animated outer ring */}
            <div
              className="absolute rounded-full border-2 border-rose-400 opacity-40 animate-ping"
              style={{
                width: `${148 + audioLevel * 0.5}px`,
                height: `${148 + audioLevel * 0.5}px`,
                transition: "width 0.1s, height 0.1s",
              }}
            />
            <div className="w-36 h-36 rounded-full bg-rose-500 flex items-center justify-center shadow-2xl shadow-rose-500/40 relative z-10">
              {/* Waveform bars */}
              <div className="flex gap-1 items-end h-10">
                {[0.6, 1, 0.7, 0.9, 0.5, 1, 0.8].map((multiplier, i) => (
                  <div
                    key={i}
                    className="w-1.5 bg-white rounded-full transition-all duration-75"
                    style={{
                      height: `${Math.max(6, audioLevel * multiplier * 0.35)}px`,
                    }}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Timer */}
          <div className="text-center">
            <div className="text-4xl font-mono font-bold text-white tabular-nums">
              {formatTime(elapsed)}
            </div>
            <div className="text-sm text-zinc-400 mt-1">
              {MAX_DURATION_SECONDS / 60}-min limit
            </div>
          </div>

          {/* Progress bar */}
          <div className="w-full bg-zinc-800 rounded-full h-1.5">
            <div
              className="bg-rose-500 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>

          {/* Stop button */}
          <button
            onClick={handleStop}
            disabled={!canStop}
            className={`px-10 py-3 rounded-full font-semibold text-base transition-all ${
              canStop
                ? "bg-white text-zinc-900 hover:bg-zinc-100 active:scale-95 shadow-lg"
                : "bg-zinc-700 text-zinc-500 cursor-not-allowed"
            }`}
          >
            {canStop ? "Stop & Generate Article" : `Generating enabled in ${MIN_DURATION_SECONDS - elapsed}s…`}
          </button>
        </>
      )}

      {/* Processing state */}
      {state === "processing" && (
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 border-4 border-zinc-600 border-t-rose-500 rounded-full animate-spin" />
          <div className="text-center">
            <p className="text-white font-semibold text-lg">Generating your article…</p>
            <p className="text-zinc-400 text-sm mt-1">
              Transcribing → Structuring → Polishing
            </p>
          </div>
        </div>
      )}

      {/* Error + reset */}
      {state === "error" && (
        <button
          onClick={handleReset}
          className="px-8 py-3 rounded-full bg-zinc-700 hover:bg-zinc-600 text-white font-semibold transition-all"
        >
          Try Again
        </button>
      )}
    </div>
  );
}
