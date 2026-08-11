export default function Privacy() {
  return (
    <div className="min-h-screen bg-ink font-body text-gray-200">
      <div className="max-w-2xl mx-auto px-8 py-16">
        <div className="flex items-center gap-3 mb-10">
          <div className="w-2.5 h-2.5 rounded-full bg-signal" />
          <span className="font-display text-lg tracking-tight text-white">
            growth<span className="text-signal">/engine</span>
          </span>
        </div>
        <h1 className="font-display text-3xl text-white mb-6">Privacy Policy</h1>
        <div className="space-y-4 text-sm leading-relaxed">
          <p>
            This app (the "Service") helps you generate marketing content and analyze
            your connected marketing accounts. This policy explains what data we
            handle and how.
          </p>
          <h2 className="font-display text-lg text-white pt-2">What we collect</h2>
          <p>
            When you connect an account (e.g. Google Search Console or Meta), we store
            the access tokens and related account identifiers needed to fetch your data.
            We also store content you generate through the app so it can be saved to
            your account.
          </p>
          <h2 className="font-display text-lg text-white pt-2">How we use it</h2>
          <p>
            Your data is used only to provide the Service: pulling your own analytics,
            generating content you request, and showing you reports inside the app.
            We do not sell your data and do not share it with third parties except the
            platforms you explicitly connect (Google, Meta) to retrieve your own data.
          </p>
          <h2 className="font-display text-lg text-white pt-2">Data retention</h2>
          <p>
            Connected-account tokens and generated content are kept while your account
            is active. You can disconnect any integration at any time; you may request
            deletion of your data by contacting the app operator.
          </p>
          <h2 className="font-display text-lg text-white pt-2">Third-party services</h2>
          <p>
            The Service uses third-party providers (hosting, AI generation, and the
            platforms you connect) that process data under their own privacy policies.
          </p>
          <h2 className="font-display text-lg text-white pt-2">Contact</h2>
          <p>Questions about this policy can be sent to the app operator.</p>
          <p className="text-mist text-xs pt-6">Last updated: August 2026</p>
        </div>
      </div>
    </div>
  );
}
