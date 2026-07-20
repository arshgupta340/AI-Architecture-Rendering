"use client";

import { FormEvent, useState } from "react";

import { createBrowserSupabase } from "@/lib/supabase/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const supabase = createBrowserSupabase();
    if (!supabase) {
      setMessage("Sign-in is not configured for this deployment.");
      return;
    }

    setPending(true);
    setMessage(null);
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback?next=/` },
    });
    setPending(false);
    setMessage(error ? error.message : "Check your email for a secure sign-in link.");
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-neutral-950 px-5 text-neutral-100">
      <form onSubmit={signIn} className="w-full max-w-sm rounded-xl border border-neutral-800 bg-neutral-900/60 p-6 shadow-2xl">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-neutral-500">Reve Canvas</p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight">Sign in</h1>
        <p className="mt-2 text-sm text-neutral-400">We’ll email you a secure magic link. No password required.</p>
        <label className="mt-6 block text-sm text-neutral-300" htmlFor="email">Email address</label>
        <input id="email" type="email" required value={email} onChange={(event) => setEmail(event.target.value)}
          className="mt-2 w-full rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm outline-none ring-neutral-500 placeholder:text-neutral-600 focus:ring-2"
          placeholder="you@studio.com" />
        <button type="submit" disabled={pending} className="mt-4 w-full rounded-lg bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-900 hover:bg-white disabled:opacity-60">
          {pending ? "Sending link…" : "Email me a sign-in link"}
        </button>
        {message && <p className="mt-4 text-sm text-neutral-400" role="status">{message}</p>}
      </form>
    </main>
  );
}
