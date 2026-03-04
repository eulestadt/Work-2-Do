"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function GeminiConfigForm({ hasConfigured }: { hasConfigured: boolean }) {
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    const res = await fetch("/api/gemini-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ apiKey }),
    });
    setLoading(false);
    if (res.ok) {
      setApiKey("");
      router.refresh();
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 max-w-md space-y-4">
      <div>
        <label htmlFor="apiKey" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
          API key
        </label>
        <input
          id="apiKey"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={hasConfigured ? "Enter new key to update" : "From Google AI Studio"}
          className="mt-1 w-full rounded border border-zinc-300 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-800"
        />
      </div>
      <button
        type="submit"
        disabled={loading || !apiKey}
        className="rounded bg-zinc-900 px-4 py-2 font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
      >
        {hasConfigured ? "Update" : "Save"} key
      </button>
    </form>
  );
}
