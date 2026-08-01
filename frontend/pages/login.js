import { useState } from "react";
import { useRouter } from "next/router";
import { supabase, supabaseConfigured } from "../lib/supabaseClient";

export default function Login() {
  const router = useRouter();
  const [mode, setMode] = useState("login"); // "login" | "signup"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      if (mode === "login") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.push("/");
      } else {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        setNotice("Check your email to confirm your account, then log in.");
        setMode("login");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-ink font-body flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="w-2.5 h-2.5 rounded-full bg-signal" />
          <span className="font-display text-lg tracking-tight text-white">
            growth<span className="text-signal">/engine</span>
          </span>
        </div>

        {!supabaseConfigured && (
          <p className="text-xs font-mono text-amber-400 bg-amber-950/30 border border-amber-800 rounded-md px-3 py-2 mb-6">
            Supabase isn't configured yet — set NEXT_PUBLIC_SUPABASE_URL and
            NEXT_PUBLIC_SUPABASE_ANON_KEY in frontend/.env.local.
          </p>
        )}

        <form onSubmit={submit} className="bg-panel border border-line rounded-lg p-6 space-y-4">
          <h1 className="font-display text-xl text-white mb-2">
            {mode === "login" ? "Log in" : "Create an account"}
          </h1>

          <div>
            <label className="block font-mono text-xs uppercase tracking-wide text-mist mb-2">
              Email
            </label>
            <input
              type="email"
              required
              className="w-full bg-ink border border-line rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-signal"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label className="block font-mono text-xs uppercase tracking-wide text-mist mb-2">
              Password
            </label>
            <input
              type="password"
              required
              minLength={6}
              className="w-full bg-ink border border-line rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-signal"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {error && <p className="text-sm text-red-400 font-mono">{error}</p>}
          {notice && <p className="text-sm text-signal font-mono">{notice}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-signal text-ink font-medium py-2.5 rounded-md hover:brightness-95 disabled:opacity-50 transition"
          >
            {loading ? "…" : mode === "login" ? "Log in" : "Sign up"}
          </button>

          <button
            type="button"
            onClick={() => setMode(mode === "login" ? "signup" : "login")}
            className="w-full text-center text-xs font-mono text-mist hover:text-white transition"
          >
            {mode === "login" ? "Need an account? Sign up" : "Already have an account? Log in"}
          </button>
        </form>
      </div>
    </div>
  );
}
