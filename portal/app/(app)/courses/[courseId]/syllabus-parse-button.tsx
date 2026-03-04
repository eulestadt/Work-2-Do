"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function SyllabusParseButton({ syllabusId }: { syllabusId: string }) {
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleParse() {
    setLoading(true);
    const res = await fetch("/api/syllabi/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ syllabusId }),
    });
    setLoading(false);
    if (res.ok) {
      router.refresh();
    } else {
      const data = await res.json();
      alert(data.error ?? "Parse failed");
    }
  }

  return (
    <button
      onClick={handleParse}
      disabled={loading}
      className="rounded bg-zinc-700 px-2 py-1 text-xs text-white hover:bg-zinc-600 disabled:opacity-50"
    >
      {loading ? "Parsing…" : "Parse with Gemini"}
    </button>
  );
}
