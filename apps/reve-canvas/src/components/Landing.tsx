"use client";

import { useRef, useState } from "react";
import { BRAND, VALUE_PROP, FEATURES } from "@/lib/brand";
import { Logo } from "./Logo";

/** Landing / upload hero: brand, value prop, drag-drop + sample, feature bullets. */
export function Landing({
  onFile,
  onSample,
  busy,
}: {
  onFile: (file: File) => void;
  onSample: () => void;
  busy: boolean;
}) {
  const [drag, setDrag] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex min-h-screen flex-col">
      {/* slim top bar */}
      <header className="flex items-center justify-between border-b border-line px-6 py-4">
        <Logo />
        <span className="font-mono text-xs text-neutral-600">v0.1 · thin slice</span>
      </header>

      <main className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-xl">
          <div className="mb-8">
            <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-accent">
              {BRAND.name} · layer-based editing
            </p>
            <h1 className="text-balance text-4xl font-semibold leading-[1.05] tracking-tight text-neutral-50 sm:text-5xl">
              Your render, in layers.
            </h1>
            <p className="mt-4 max-w-md text-pretty text-base leading-relaxed text-neutral-400">
              {VALUE_PROP}
            </p>
          </div>

          {/* drag-drop zone */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              const f = e.dataTransfer.files?.[0];
              if (f) onFile(f);
            }}
            onClick={() => fileRef.current?.click()}
            className={`group flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed px-8 py-14 text-center transition-colors ${
              drag
                ? "border-accent bg-accent/5"
                : "border-neutral-800 bg-neutral-900/40 hover:border-neutral-600"
            }`}
          >
            <div className="mb-4 grid h-12 w-12 place-items-center rounded-xl border border-neutral-700 bg-neutral-900 text-2xl text-accent">
              ↑
            </div>
            <p className="text-sm text-neutral-200">
              Drop a viewport screenshot, render, or photo
            </p>
            <p className="mt-1 text-xs text-neutral-500">
              {BRAND.name} reads it into editable architectural layers
            </p>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
            />
          </div>

          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={onSample}
              disabled={busy}
              className="rounded-lg bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-900 transition-colors hover:bg-white disabled:opacity-50"
            >
              Use sample building
            </button>
            <span className="text-xs text-neutral-600">
              or drag an image above
            </span>
          </div>

          {/* quiet feature bullets */}
          <ul className="mt-10 grid gap-3">
            {FEATURES.map((f) => (
              <li key={f.title} className="flex items-start gap-3">
                <span
                  className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                  style={{ background: BRAND.accent }}
                />
                <div>
                  <p className="text-sm font-medium text-neutral-200">{f.title}</p>
                  <p className="text-xs text-neutral-500">{f.detail}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </main>

      <footer className="border-t border-line px-6 py-4 text-center text-xs text-neutral-700">
        {BRAND.name} — architecture-native layer editing · no re-render of the world
      </footer>
    </div>
  );
}
