import { useEffect, useState } from "react";
import Link from "next/link";
import { supabase, supabaseConfigured } from "../lib/supabaseClient";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const CONTENT_TYPES = [
  { key: "blog", label: "Blog Post", endpoint: "/generate/blog" },
  { key: "landing-page", label: "Landing Page", endpoint: "/generate/landing-page" },
  { key: "ad", label: "Text Ad", endpoint: "/generate/ad" },
  { key: "video-script", label: "Video Script", endpoint: "/generate/video-script" },
];

export default function Home() {
  const [form, setForm] = useState({
    product_name: "",
    target_audience: "",
    goal: "",
    tone: "confident and clear",
    key_points: "",
  });
  const [activeType, setActiveType] = useState("blog");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [runCount, setRunCount] = useState(0);
  const [audit, setAudit] = useState(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [ads, setAds] = useState(null);
  const [adsLoading, setAdsLoading] = useState(false);
  const [session, setSession] = useState(null);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [linkedinStatus, setLinkedinStatus] = useState(null);
  const [banner, setBanner] = useState(null);

  useEffect(() => {
    if (!supabaseConfigured) {
      setSessionChecked(true);
      return;
    }
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setSessionChecked(true);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  const logout = async () => {
    await supabase.auth.signOut();
  };

  const loadLinkedinStatus = async () => {
    if (!session) return;
    try {
      const res = await fetch(`${BACKEND_URL}/auth/linkedin/status`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (res.ok) setLinkedinStatus(await res.json());
    } catch (e) {
      // header stays on the plain "Connect LinkedIn" state
    }
  };

  useEffect(() => {
    if (session) loadLinkedinStatus();
  }, [session]);

  const disconnectLinkedin = async () => {
    if (!window.confirm("Disconnect LinkedIn?")) return;
    try {
      await fetch(`${BACKEND_URL}/auth/linkedin/disconnect`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      setLinkedinStatus({ connected: false });
      setBanner({ type: "success", text: "LinkedIn disconnected." });
    } catch (e) {
      setBanner({ type: "error", text: "Couldn't disconnect LinkedIn." });
    }
  };

  useEffect(() => {
    if (!session) return;
    const params = new URLSearchParams(window.location.search);
    const connected = params.get("connected");
    const error = params.get("error");
    if (connected === "google_search_console") {
      const siteUrl = window.prompt(
        "Connected! Which verified Search Console property should we monitor? " +
          "(e.g. https://example.com/ or sc-domain:example.com)"
      );
      if (siteUrl) {
        fetch(
          `${BACKEND_URL}/auth/google/set-site?user_id=${session.user.id}&site_url=${encodeURIComponent(siteUrl)}`,
          { method: "POST" }
        );
      }
      setBanner({ type: "success", text: "Search Console connected." });
    } else if (connected === "linkedin") {
      setBanner({ type: "success", text: "LinkedIn connected." });
    } else if (error) {
      const messages = {
        linkedin_invalid_scope:
          "LinkedIn rejected the login — the app is missing the 'Sign In with LinkedIn using OpenID Connect' product. Add it under Products in your LinkedIn developer app (linkedin.com/developers/apps), then try again.",
        linkedin_cancelled: "LinkedIn login was cancelled.",
        linkedin_denied: "LinkedIn login was cancelled or denied.",
        linkedin_no_user: "You need to be logged in before connecting LinkedIn.",
        linkedin_not_configured: "LinkedIn isn't configured on the server yet — try again in a few minutes.",
        linkedin_auth_failed: "LinkedIn authorization failed. Please try again.",
      };
      setBanner({
        type: "error",
        text:
          messages[error] ||
          `Connection failed (${error}). Please try again.`,
      });
    }
    if (connected || error) {
      window.history.replaceState({}, "", "/");
      loadLinkedinStatus();
    }
  }, [session]);

  const loadMockAudit = async () => {
    setAuditLoading(true);
    try {
      // Logged in + connected to Search Console -> real numbers.
      // Otherwise fall back to the demo report so the panel still shows something.
      let data = null;
      if (session?.access_token) {
        const real = await fetch(`${BACKEND_URL}/audit/search-console-report`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
        if (real.ok) {
          data = await real.json();
          setAudit(data);
          setAuditLoading(false);
          return;
        }
      }
      const res = await fetch(`${BACKEND_URL}/audit/mock-report`);
      data = await res.json();
      setAudit(data);
    } catch (e) {
      // silent - audit panel is a bonus, not the main flow
    } finally {
      setAuditLoading(false);
    }
  };

  useEffect(() => {
    if (!sessionChecked) return;
    loadMockAudit();
    loadAdsHealth();
  }, [session, sessionChecked]);

  const loadAdsHealth = async () => {
    setAdsLoading(true);
    try {
      // Logged in + Meta connected -> real ads data. Otherwise demo report.
      let data = null;
      if (session?.access_token) {
        const real = await fetch(`${BACKEND_URL}/ads/health`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
        if (real.ok) {
          data = await real.json();
          setAds(data);
          setAdsLoading(false);
          return;
        }
      }
      const res = await fetch(`${BACKEND_URL}/ads/mock-report`);
      data = await res.json();
      setAds(data);
    } catch (e) {
      // silent - ads panel is a bonus, not the main flow
    } finally {
      setAdsLoading(false);
    }
  };

  const handleChange = (field) => (e) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const generate = async () => {
    if (!form.product_name || !form.target_audience || !form.goal) {
      setError("Fill in product, audience, and goal first.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const endpoint = CONTENT_TYPES.find((c) => c.key === activeType).endpoint;
      const headers = { "Content-Type": "application/json" };
      if (session?.access_token) {
        headers["Authorization"] = `Bearer ${session.access_token}`;
      }
      const res = await fetch(`${BACKEND_URL}${endpoint}`, {
        method: "POST",
        headers,
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error(`Backend returned ${res.status}`);
      const data = await res.json();
      setResult(data);
      setRunCount((n) => n + 1);
    } catch (err) {
      setError(
        `Couldn't reach the generation backend (${err.message}). Is it running at ${BACKEND_URL}?`
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-ink font-body">
      {/* Header */}
      <header className="border-b border-line px-8 py-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-signal" />
          <span className="font-display text-lg tracking-tight text-white">
            growth<span className="text-signal">/engine</span>
          </span>
        </div>
        <div className="flex items-center gap-6">
          <div className="font-mono text-xs text-mist">
            content generated this session — <span className="text-signal">{runCount}</span>
          </div>
          {session ? (
            <>
              <a
                href={`${BACKEND_URL}/auth/google/login?user_id=${session.user.id}`}
                className="font-mono text-xs border border-line rounded px-3 py-1.5 text-mist hover:text-white hover:border-mist transition"
              >
                Connect Search Console
              </a>
              <a
                href={`${BACKEND_URL}/auth/meta/login?user_id=${session.user.id}`}
                className="font-mono text-xs border border-line rounded px-3 py-1.5 text-mist hover:text-white hover:border-mist transition"
              >
                Connect Meta Ads
              </a>
              {linkedinStatus?.connected ? (
                <span className="flex items-center gap-2 font-mono text-xs text-mist">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
                  LinkedIn: {linkedinStatus.account_label || "connected"}
                  <button
                    onClick={disconnectLinkedin}
                    title="Disconnect LinkedIn"
                    className="border border-line rounded px-2 py-1 text-mist hover:text-red-400 hover:border-red-400/50 transition"
                  >
                    Disconnect
                  </button>
                </span>
              ) : (
                <a
                  href={`${BACKEND_URL}/auth/linkedin/login?user_id=${session.user.id}`}
                  className="font-mono text-xs border border-line rounded px-3 py-1.5 text-mist hover:text-white hover:border-mist transition"
                >
                  Connect LinkedIn
                </a>
              )}
              <Link
                href="/feed"
                className="font-mono text-xs border border-line rounded px-3 py-1.5 text-mist hover:text-white hover:border-mist transition"
              >
                Auto-suggested feed
              </Link>
              <span className="font-mono text-xs text-mist">{session.user.email}</span>
              <button
                onClick={logout}
                className="font-mono text-xs text-mist hover:text-white transition"
              >
                Log out
              </button>
            </>
          ) : (
            sessionChecked && (
              <Link
                href="/login"
                className="font-mono text-xs border border-line rounded px-3 py-1.5 text-mist hover:text-white hover:border-mist transition"
              >
                Log in to save your work
              </Link>
            )
          )}
        </div>
      </header>

      {/* OAuth result banner — success or failure after a connect attempt */}
      {banner && (
        <div className="max-w-6xl mx-auto px-8 pt-6">
          <div
            className={`border rounded-lg px-4 py-3 font-mono text-sm ${
              banner.type === "error"
                ? "border-red-500/40 bg-red-950/40 text-red-300"
                : "border-green-500/40 bg-green-950/40 text-green-300"
            }`}
          >
            {banner.text}
            <button
              onClick={() => setBanner(null)}
              className="float-right text-mist hover:text-white transition"
              aria-label="Dismiss"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Audit strip — mock data until Search Console is connected */}
      <div className="max-w-6xl mx-auto px-8 pt-8">
        <div className="bg-panel border border-line rounded-lg px-6 py-4">
          <div className="flex items-center justify-between mb-3">
            <span className="font-mono text-xs uppercase tracking-wide text-mist">
              SEO snapshot {audit ? "" : "(loading…)"}
            </span>
            {audit?.seo_score !== undefined && (
              <span className="font-display text-2xl text-signal">{audit.seo_score}/100</span>
            )}
          </div>
          {audit && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-mist text-xs mb-1">Findings</div>
                <ul className="space-y-1 text-gray-200">
                  {audit.findings?.map((f, i) => <li key={i}>• {f}</li>)}
                </ul>
              </div>
              <div>
                <div className="text-mist text-xs mb-1">Recommended actions</div>
                <ul className="space-y-1 text-gray-200">
                  {audit.recommended_actions?.map((a, i) => <li key={i}>→ {a}</li>)}
                </ul>
              </div>
            </div>
          )}
          <p className="font-mono text-[11px] text-mist mt-3">
            {session
              ? "Live data from your connected Search Console account (falls back to sample data if none connected)."
              : "Based on sample data — log in and click \"Connect Search Console\" for your real numbers."}
          </p>
        </div>
      </div>

      {/* Ads Health strip — real Meta ads data when connected, demo otherwise */}
      <div className="max-w-6xl mx-auto px-8 pt-6">
        <div className="bg-panel border border-line rounded-lg px-6 py-4">
          <div className="flex items-center justify-between mb-3">
            <span className="font-mono text-xs uppercase tracking-wide text-mist">
              Ads health {adsLoading ? "(loading…)" : ""}
            </span>
            {ads?.ads_score !== undefined && (
              <span className="font-display text-2xl text-signal">{ads.ads_score}/100</span>
            )}
          </div>
          {ads?.label && (
            <div className="font-mono text-[11px] uppercase tracking-wide mb-3">
              <span
                className={`px-2 py-0.5 rounded ${
                  ads.label === "healthy"
                    ? "bg-green-900/40 text-green-300"
                    : ads.label === "needs attention"
                    ? "bg-amber-900/40 text-amber-300"
                    : "bg-red-900/40 text-red-300"
                }`}
              >
                {ads.label}
              </span>
            </div>
          )}
          {ads && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-mist text-xs mb-1">Findings</div>
                <ul className="space-y-1 text-gray-200">
                  {ads.findings?.map((f, i) => <li key={i}>• {f}</li>)}
                </ul>
              </div>
              <div>
                <div className="text-mist text-xs mb-1">Recommended actions</div>
                <ul className="space-y-1 text-gray-200">
                  {ads.recommended_actions?.map((a, i) => <li key={i}>→ {a}</li>)}
                </ul>
              </div>
            </div>
          )}
          {ads?.commentary && (
            <p className="text-sm text-gray-300 italic mt-3 border-t border-line pt-3">
              {ads.commentary}
            </p>
          )}
          <p className="font-mono text-[11px] text-mist mt-3">
            {ads?.is_mock
              ? "Sample data — log in and click \"Connect Meta Ads\" to analyze your real campaigns."
              : "Live analysis of your connected Meta ad account."}
          </p>
        </div>
      </div>

      <main className="max-w-6xl mx-auto px-8 py-12 grid grid-cols-1 lg:grid-cols-5 gap-10">
        {/* Left: input form */}
        <section className="lg:col-span-2">
          <h1 className="font-display text-3xl text-white leading-tight mb-2">
            Tell it what you're selling.
          </h1>
          <p className="text-mist text-sm mb-8">
            It writes the blog, the page, the ad, and the script.
          </p>

          <div className="space-y-5">
            <Field
              label="Product or service"
              value={form.product_name}
              onChange={handleChange("product_name")}
              placeholder="e.g. AI Accounting Software"
            />
            <Field
              label="Target audience"
              value={form.target_audience}
              onChange={handleChange("target_audience")}
              placeholder="e.g. Small business owners"
            />
            <Field
              label="Goal"
              value={form.goal}
              onChange={handleChange("goal")}
              placeholder="e.g. Get email signups"
            />
            <Field
              label="Tone"
              value={form.tone}
              onChange={handleChange("tone")}
              placeholder="e.g. confident and clear"
            />
            <div>
              <label className="block font-mono text-xs uppercase tracking-wide text-mist mb-2">
                Extra context (optional)
              </label>
              <textarea
                className="w-full bg-panel border border-line rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-signal"
                rows={3}
                value={form.key_points}
                onChange={handleChange("key_points")}
                placeholder="Offers, differentiators, facts to include..."
              />
            </div>
          </div>

          {/* Content type tabs */}
          <div className="mt-8">
            <label className="block font-mono text-xs uppercase tracking-wide text-mist mb-2">
              Format
            </label>
            <div className="flex flex-wrap gap-2">
              {CONTENT_TYPES.map((c) => (
                <button
                  key={c.key}
                  onClick={() => setActiveType(c.key)}
                  className={`px-3 py-1.5 rounded-md text-sm border transition ${
                    activeType === c.key
                      ? "bg-signal text-ink border-signal font-medium"
                      : "border-line text-mist hover:text-white hover:border-mist"
                  }`}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={generate}
            disabled={loading}
            className="mt-8 w-full bg-signal text-ink font-medium py-3 rounded-md hover:brightness-95 disabled:opacity-50 transition"
          >
            {loading ? "Generating…" : "Generate content"}
          </button>

          {error && (
            <p className="mt-4 text-sm text-red-400 font-mono">{error}</p>
          )}
        </section>

        {/* Right: output preview */}
        <section className="lg:col-span-3">
          <div className="bg-panel border border-line rounded-lg min-h-[500px] p-8">
            <div className="font-mono text-xs uppercase tracking-wide text-mist mb-6">
              Output — {CONTENT_TYPES.find((c) => c.key === activeType)?.label}
            </div>
            {!result && !loading && (
              <p className="text-mist text-sm">
                Nothing generated yet. Fill in the form and hit generate.
              </p>
            )}
            {loading && <p className="text-signal font-mono text-sm">Writing…</p>}
            {result && <ResultView type={activeType} data={result} />}
          </div>
        </section>
      </main>
    </div>
  );
}

function Field({ label, value, onChange, placeholder }) {
  return (
    <div>
      <label className="block font-mono text-xs uppercase tracking-wide text-mist mb-2">
        {label}
      </label>
      <input
        className="w-full bg-panel border border-line rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-signal"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
      />
    </div>
  );
}

function ResultView({ type, data }) {
  if (type === "blog") {
    return (
      <div className="space-y-4">
        <h2 className="font-display text-2xl text-white">{data.title}</h2>
        <p className="text-mist text-sm italic">{data.meta_description}</p>
        <div className="flex flex-wrap gap-2">
          {data.target_keywords?.map((k) => (
            <span key={k} className="font-mono text-xs bg-ink border border-line rounded px-2 py-1 text-signal">
              {k}
            </span>
          ))}
        </div>
        <pre className="whitespace-pre-wrap text-sm text-gray-200 leading-relaxed font-body">
          {data.body_markdown}
        </pre>
      </div>
    );
  }
  if (type === "landing-page") {
    return (
      <div className="space-y-4">
        <h2 className="font-display text-2xl text-white">{data.headline}</h2>
        <p className="text-mist">{data.subheadline}</p>
        <ul className="list-disc list-inside text-gray-200 space-y-1">
          {data.benefits?.map((b) => <li key={b}>{b}</li>)}
        </ul>
        <button className="bg-signal text-ink px-4 py-2 rounded-md font-medium">
          {data.cta_text}
        </button>
      </div>
    );
  }
  if (type === "ad") {
    return (
      <div className="space-y-3">
        <h2 className="font-display text-xl text-white">{data.headline}</h2>
        <p className="text-gray-200">{data.primary_text}</p>
        <p className="font-mono text-sm text-signal">
          {data.hashtags?.map((h) => `#${h}`).join(" ")}
        </p>
      </div>
    );
  }
  if (type === "video-script") {
    return (
      <div className="space-y-4">
        {data.scenes?.map((s, i) => (
          <div key={i} className="border-l-2 border-signal pl-4">
            <div className="font-mono text-xs text-signal uppercase">{s.scene}</div>
            <div className="text-sm text-mist mb-1">{s.visual_suggestion}</div>
            <div className="text-gray-200">{s.voiceover_text}</div>
          </div>
        ))}
      </div>
    );
  }
  return null;
}
