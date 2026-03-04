"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function SyllabusUpload({ courseId }: { courseId: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    const formData = new FormData();
    formData.set("file", file);
    formData.set("courseId", courseId);
    const res = await fetch("/api/syllabi/upload", {
      method: "POST",
      body: formData,
    });
    setLoading(false);
    if (res.ok) {
      setFile(null);
      router.refresh();
    }
  }

  return (
    <form onSubmit={handleUpload} className="mt-2 flex items-end gap-2">
      <input
        type="file"
        accept=".pdf,.txt"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="text-sm"
      />
      <button
        type="submit"
        disabled={!file || loading}
        className="rounded bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
      >
        Upload
      </button>
    </form>
  );
}
