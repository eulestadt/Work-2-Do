"use client";

import { useState, useEffect } from "react";

export default function AppConnectionPage() {
  const [keys, setKeys] = useState<Array<{ id: string; label: string | null; createdAt: string }>>([]);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [label, setLabel] = useState("");
  const [loading, setLoading] = useState(false);
  const [baseUrl, setBaseUrl] = useState("");

  useEffect(() => {
    setBaseUrl(typeof window !== "undefined" ? window.location.origin : "");
  }, []);

  const loadKeys = async () => {
    const res = await fetch("/api/app-keys");
    if (res.ok) {
      const { keys: k } = await res.json();
      setKeys(k);
    }
  };

  useEffect(() => {
    loadKeys();
  }, []);

  const createKey = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/app-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label: label || null }),
      });
      const data = await res.json();
      if (res.ok && data.key) {
        setNewKey(data.key);
        setLabel("");
        loadKeys();
      } else {
        alert(data.error || "Failed to create key");
      }
    } finally {
      setLoading(false);
    }
  };

  const revokeKey = async (id: string) => {
    if (!confirm("Revoke this API key? The app using it will stop working.")) return;
    const res = await fetch(`/api/app-keys/${id}`, { method: "DELETE" });
    if (res.ok) {
      setNewKey(null);
      loadKeys();
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold">App connection</h1>
      <p className="mt-1 text-zinc-600 dark:text-zinc-400">
        Connect the GetWorkToDo iOS app to this portal using an API key.
      </p>

      <div className="mt-6 space-y-6">
        <section>
          <h2 className="text-lg font-medium">Base URL</h2>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Paste this URL in the app Settings as the backend URL:
          </p>
          <code className="mt-2 block rounded bg-zinc-100 px-3 py-2 font-mono text-sm dark:bg-zinc-800">
            {baseUrl}
          </code>
        </section>

        <section>
          <h2 className="text-lg font-medium">API key</h2>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Generate a key and paste it in the app when prompted. The app will send it with each request.
          </p>
          <div className="mt-3 flex gap-2">
            <input
              type="text"
              placeholder="Label (e.g. iPhone)"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="rounded border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-800"
            />
            <button
              onClick={createKey}
              disabled={loading}
              className="rounded bg-zinc-900 px-4 py-2 text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
            >
              {loading ? "Creating..." : "Generate API key"}
            </button>
          </div>
          {newKey && (
            <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/30">
              <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                Copy this key now. It will not be shown again.
              </p>
              <code className="mt-2 block break-all font-mono text-sm">{newKey}</code>
            </div>
          )}
        </section>

        <section>
          <h2 className="text-lg font-medium">Your API keys</h2>
          {keys.length === 0 ? (
            <p className="text-sm text-zinc-600 dark:text-zinc-400">No keys yet.</p>
          ) : (
            <ul className="mt-2 space-y-2">
              {keys.map((k) => (
                <li
                  key={k.id}
                  className="flex items-center justify-between rounded border border-zinc-200 px-3 py-2 dark:border-zinc-700"
                >
                  <span className="text-sm">
                    {k.label || "Unlabeled"} · created {new Date(k.createdAt).toLocaleDateString()}
                  </span>
                  <button
                    onClick={() => revokeKey(k.id)}
                    className="text-sm text-red-600 hover:underline dark:text-red-400"
                  >
                    Revoke
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
