"use client";

import { useEffect, useRef, useState } from "react";
import { mediaUrl } from "@/lib/api";
import type { ProjectDetail } from "@/lib/types";

function clock(value: number) {
  return `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`;
}

export function RecordingEvidence({ project }: { project: ProjectDetail }) {
  const video = useRef<HTMLVideoElement>(null);
  const [time, setTime] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const viewer = useRef<HTMLDivElement>(null);
  const expandButton = useRef<HTMLButtonElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const scrollPosition = useRef(0);
  useEffect(() => {
    if (!expanded) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButton.current?.focus({ preventScroll: true });
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); setExpanded(false); return; }
      if (event.key !== "Tab") return;
      const items = viewer.current?.querySelectorAll<HTMLElement>("video, button");
      if (!items?.length) return;
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", handleKey, true);
    return () => {
      document.removeEventListener("keydown", handleKey, true);
      document.body.style.overflow = previousOverflow;
      window.scrollTo(0, scrollPosition.current);
      expandButton.current?.focus({ preventScroll: true });
    };
  }, [expanded]);
  const media = project.media;
  if (!media) return null;
  const seek = (timestamp: number) => {
    if (video.current) video.current.currentTime = timestamp;
    setTime(timestamp);
  };
  return (
    <section aria-label="Recording evidence" className="mt-8 rounded-[28px] border border-line bg-white/[0.03] p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-wider text-signal">Recording evidence</p>
          <h2 className="mt-2 font-serif text-3xl">Listen. See. Trace the source.</h2>
          <p className="mt-2 max-w-3xl text-sm text-ink/60">FFmpeg separates the audio and timestamped frames. Gladia transcribes the narration; H Company interprets the frames. Recorded demonstrations are observations, not independently verified capabilities.</p>
        </div>
        <span className="font-mono text-xs text-ink/60">{clock(media.duration)} · {media.frames.length} sampled frames</span>
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <div className="min-w-0">
          {media.has_video && <>
            <div ref={viewer} role={expanded ? "dialog" : undefined} aria-modal={expanded ? true : undefined}
              aria-label={expanded ? "Expanded recording" : undefined}
              className={expanded ? "fixed inset-0 z-[100] bg-black" : "relative"}>
              <video ref={video} controls playsInline preload="metadata" src={mediaUrl(project.id, "original")}
                onTimeUpdate={(event) => setTime(event.currentTarget.currentTime)}
                className={expanded ? "h-full w-full bg-black object-contain" : "aspect-video w-full rounded-xl bg-black"} />
              {expanded && <>
                <span className="absolute left-3 top-3 hidden rounded-lg bg-ink/90 px-2 py-3 text-xs text-ink/75 2xl:block">Recorded source</span>
                <button ref={closeButton} type="button" onClick={() => setExpanded(false)}
                  className="absolute right-3 top-3 min-h-11 rounded-lg border border-line bg-ink px-3 text-sm text-ink hover:border-signal">Return to evidence</button>
              </>}
            </div>
            <button ref={expandButton} type="button" onClick={() => { scrollPosition.current = window.scrollY; setExpanded(true); }}
              className={expanded ? "hidden" : "mt-3 min-h-11 rounded-lg border border-line px-4 text-sm hover:border-signal"}>Expand recording</button>
          </>}
          {media.has_audio && <details className="mt-3 rounded-xl border border-line p-3 text-sm">
            <summary>Extracted audio track</summary>
            <audio controls preload="none" src={mediaUrl(project.id, "audio.wav")} className="mt-3 w-full" />
          </details>}
          <p className="mt-3 break-all font-mono text-[10px] text-ink/40">Source SHA-256: {media.source_sha256}</p>
        </div>
        <div className="max-h-[460px] space-y-3 overflow-y-auto rounded-xl border border-line p-4">
          <h3 className="font-mono text-xs uppercase text-signal">Narration transcript</h3>
          {!project.transcripts.length && <p className="text-sm text-ink/60">No usable transcript yet. The visual frames can still be assessed separately.</p>}
          {project.transcripts.map((segment) => <button type="button" key={segment.id} onClick={() => seek(segment.start)}
            className={`block w-full rounded-lg p-2 text-left text-sm leading-relaxed hover:bg-white/5 ${time >= segment.start && time < segment.end ? "bg-signal/10" : ""}`}>
            <span className="mr-2 font-mono text-xs text-signal">{clock(segment.start)}</span>{segment.text}
          </button>)}
        </div>
      </div>
      <div className="mt-5 flex gap-3 overflow-x-auto pb-2">
        {media.frames.map((frame) => <button key={frame.image} type="button" onClick={() => seek(frame.timestamp)}
          aria-label={`Seek recording to ${clock(frame.timestamp)}`} className="w-40 shrink-0 overflow-hidden rounded-lg border border-line text-left hover:border-signal">
          <img src={mediaUrl(project.id, frame.image)} alt={`Recorded interface at ${clock(frame.timestamp)}`} className="aspect-video w-full object-contain" />
          <span className="block px-2 py-1 font-mono text-xs text-signal">{clock(frame.timestamp)}</span>
        </button>)}
      </div>
      <details className="mt-4 border-t border-line pt-4 text-sm">
        <summary>H Company frame interpretation and product identity</summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {media.observations.map((item) => <div key={item.timestamp} className="rounded-xl border border-line p-3">
            <p className="font-mono text-xs text-signal">{clock(item.timestamp)} · {item.result.same_product === true ? "Product matched" : "Not admitted to knowledge"}</p>
            <p className="mt-2 text-ink/60">{item.error || item.result.product_reason}</p>
            {item.result.observations?.map((observation, index) => <p className="mt-2 text-ink/80" key={index}><strong>{observation.control}:</strong> {observation.observation}</p>)}
            {item.result.limitations?.map((limit, index) => <p className="mt-1 text-clay" key={index}>{limit}</p>)}
          </div>)}
        </div>
      </details>
    </section>
  );
}
