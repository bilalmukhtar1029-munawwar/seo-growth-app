import { useEffect, useState } from "react";
import Link from "next/link";
import { supabase, supabaseConfigured } from "../lib/supabaseClient";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const TYPE_LABELS = {
  blog: "Blog",
  landing_page: "Landing Page",
  ad: "Ad",
  video_script: "Video Script",
  linkedin_post: "LinkedIn Post",
};

export default function Feed() {
  const [session, setSession] = useState(null);
  const [drafts, setDrafts] = useState(null);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);

  useEffect(() => {
    if (!supabaseConfigured) return;
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
  }, []);

  useEffect(() => {
    if (!session) return;
    loadFeed();
  }, [session]);

  const authHeaders = () => ({ Authorization: `Bearer ${session.access_token}` });

  const loadFeed = async () => {
    setError(null);
    try {
      const res = await fetch(`${BACKEND_URL}/feed/`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`Backend returned ${res.status}`);
      setDrafts(await res.json());
    } catch (err) {
      setError(`Couldn't load the feed (${err.message}). Is the backend running?`);
    }
  };

  const runScan = async () => {
    setScanning(true);
    setError(null);
    setScanResult(null);
    try {
      const res = await fetch(`${BACKEND_URL}/feed/scan`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`Backend returned ${res.status}`);
      const data = await res.json();
      setScanResult(data.scans || {});
      await loadFeed();
    } catch (err) {
      setError(`Scan failed: ${err.message}`);
    } finally {
      setScanning(false);
    }
  };

  const scanSummary = () => {
    if (!scanResult) return null;
    const bits = [];
    const gsc = scanResult.search_console;
    if (gsc) {
      if (gsc.error) bits.push(`Search Console: error (${gsc.error})`);
      else if (gsc.drafts_created !== undefined) bits.push(`Search Console: ${gsc.drafts_created} draft(s)`);
      else if (gsc.skipped) bits.push(`Search Console: ${gsc.skipped}`);
    }
    const li = scanResult.linkedin;
    if (li) {
      if (li.error) bits.push(`LinkedIn: error (${li.error})`);
      else if (li.drafts_created !== undefined)
        bits.push(`LinkedIn: ${li.drafts_created} draft(s)${li.skipped_duplicates ? ` (${li.skipped_duplicates} duplicate(s) skipped)` : ""}`);
      else if (li.skipped) bits.push(`LinkedIn: ${li.skipped}`);
    }
    return bits.length ? bits.join(" • ") : "Scan done — nothing new to add.";
  };

  const act = async (draftId, action) => {
    setBusyId(draftId);
    try {
      const url = `${BACKEND_URL}/feed/${draftId}${action === "approve" ? "/approve" : ""}`;
      const res = await fetch(url, {
        method: action === "approve" ? "POST" : "DELETE",
        headers: authHeaders(),
      });
      if (action === "approve") {
        const data = await res.json();
        if (data.wordpress?.wp_edit_link) {
          window.alert(`Pushed to WordPress as a draft: ${data.wordpress.wp_edit_link}`);
        } else if (data.wordpress?.error) {
          window.alert(`Approved, but WordPress publish failed: ${data.wordpress.error}`);
        }
      }
      setDrafts((d) => d.filter((x) => x.id !== draftId));
    } catch (err) {
      setError(`Action failed: ${err.message}`);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="min-h-screen bg-ink font-body">
      <header className="border-b border-line px-8 py-5 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-signal" />
          <span className="font-display text-lg tracking-tight text-white">
            growth<span className="text-signal">/engine</span>
          </span>
        </Link>
        <Link href="/" className="font-mono text-xs text-mist hover:text-white transition">
          ← Back to generator
        </Link>
      </header>

      <main className="max-w-3xl mx-auto px-8 py-12">
        <div className="flex items-center justify-between mb-1">
          <h1 className="font-display text-2xl text-white">Auto-suggested content</h1>
          {session && (
            <button
              onClick={runScan}
              disabled={scanning}
              className="bg-signal text-ink text-sm font-medium px-4 py-1.5 rounded-md disabled:opacity-50 transition"
            >
              {scanning ? "Scanning…" : "Run scan now"}
            </button>
          )}
        </div>
        <p className="text-mist text-sm mb-3">
          Drafted automatically from gaps found in your connected accounts. Approve to
          keep, dismiss to discard — nothing publishes on its own.
        </p>
        {scanResult && (
          <p className="font-mono text-xs text-signal mb-6">{scanSummary()}</p>
        )}

        {!session && (
          <p className="text-mist text-sm">
            <Link href="/login" className="text-signal underline">
              Log in
            </Link>{" "}
            to see your feed.
          </p>
        )}

        {session && drafts === null && !error && (
          <p className="text-mist text-sm font-mono">Loading…</p>
        )}

        {error && <p className="text-red-400 text-sm font-mono mb-4">{error}</p>}

        {drafts?.length === 0 && (
          <div className="text-mist text-sm space-y-2">
            <p>
              Nothing here yet — hit <span className="text-signal">Run scan now</span> to check
              your connected accounts for gaps right away, or wait for the weekly scan.
            </p>
            <p className="text-xs">
              Connect <span className="text-signal">Search Console</span> to draft blog posts from
              underperforming pages, or connect <span className="text-signal">LinkedIn</span> to
              turn your approved content into LinkedIn posts — both from the generator page.
            </p>
          </div>
        )}

        <div className="space-y-4">
          {drafts?.map((d) => (
            <div key={d.id} className="bg-panel border border-line rounded-lg p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-[10px] uppercase tracking-wide text-signal bg-ink border border-line rounded px-2 py-0.5">
                  {TYPE_LABELS[d.content_type] || d.content_type}
                </span>
                <span className="font-mono text-[10px] text-mist">
                  {new Date(d.created_at).toLocaleDateString()}
                </span>
              </div>
              <h2 className="font-display text-lg text-white mb-1">
                {d.payload?.title || d.product_name}
              </h2>
              {d.payload?.meta_description && (
                <p className="text-mist text-sm mb-3">{d.payload.meta_description}</p>
              )}
              <p className="text-gray-300 text-sm line-clamp-3 mb-4">
                {(d.payload?.body_markdown || "").slice(0, 220)}…
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => act(d.id, "approve")}
                  disabled={busyId === d.id}
                  className="bg-signal text-ink text-sm font-medium px-4 py-1.5 rounded-md disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  onClick={() => act(d.id, "dismiss")}
                  disabled={busyId === d.id}
                  className="border border-line text-mist text-sm px-4 py-1.5 rounded-md hover:text-white disabled:opacity-50"
                >
                  Dismiss
                </button>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
