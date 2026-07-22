"use client";

import { useState } from "react";
import LoginHero from "@/components/LoginHero";
import { createClient } from "@/lib/supabase/client";

const inputClass =
  "w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-2.5 font-mono text-xs text-zinc-200 outline-none transition-colors placeholder:text-zinc-600 focus:border-amber-600";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const supabase = createClient();
    const { error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (authError) {
      setError(authError.message);
      setLoading(false);
      return;
    }

    window.location.href = "/terminal";
  }

  return (
    <div className="grid h-[100dvh] min-h-screen overflow-hidden lg:grid-cols-2">
      {/* Formulario */}
      <div className="flex flex-col justify-center bg-zinc-950 px-6 py-12 sm:px-12 lg:px-16">
        <div className="mx-auto w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2">
            <span className="font-mono text-lg text-amber-500">▮</span>
            <div>
              <h1 className="font-sans text-base font-semibold tracking-wide text-zinc-100">
                X Scraper Terminal
              </h1>
              <p className="font-mono text-[10px] text-zinc-600">Operator access</p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label
                htmlFor="email"
                className="mb-1.5 block font-mono text-[10px] uppercase tracking-wider text-zinc-500"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="operator@email.com"
                required
                autoComplete="email"
                className={inputClass}
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-1.5 block font-mono text-[10px] uppercase tracking-wider text-zinc-500"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="current-password"
                className={inputClass}
              />
            </div>

            {error && (
              <p className="font-mono text-xs text-red-400">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded border border-zinc-700 bg-zinc-900 py-2.5 font-sans text-xs font-medium text-zinc-200 transition-colors hover:border-amber-600 hover:text-amber-400 disabled:opacity-50"
            >
              {loading ? "Signing in…" : "Enter Terminal"}
            </button>
          </form>

          <p className="mt-8 font-mono text-[10px] leading-relaxed text-zinc-600">
            Personal financial research workspace. Signups disabled — invited
            operators only.
          </p>
        </div>
      </div>

      {/* Hero visual — oculto en mobile */}
      <div className="hidden h-full min-h-screen lg:block">
        <LoginHero />
      </div>
    </div>
  );
}
