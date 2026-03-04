"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function CourseForm({ userId, course }: { userId: string; course?: { id: string; title: string; term?: string | null; populiCourseCode?: string | null } }) {
  const [title, setTitle] = useState(course?.title ?? "");
  const [term, setTerm] = useState(course?.term ?? "");
  const [populiCode, setPopuliCode] = useState(course?.populiCourseCode ?? "");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    const res = await fetch(course ? `/api/courses/${course.id}` : "/api/courses", {
      method: course ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, term, populiCourseCode: populiCode || undefined }),
    });
    setLoading(false);
    if (res.ok) {
      const data = await res.json();
      router.push(`/courses/${data.id ?? course?.id}`);
      router.refresh();
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 max-w-md space-y-4">
      <div>
        <label htmlFor="title" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Title
        </label>
        <input
          id="title"
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="mt-1 w-full rounded border border-zinc-300 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-800"
        />
      </div>
      <div>
        <label htmlFor="term" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Term
        </label>
        <input
          id="term"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          placeholder="e.g. Spring 2026"
          className="mt-1 w-full rounded border border-zinc-300 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-800"
        />
      </div>
      <div>
        <label htmlFor="populi" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Populi course code (optional)
        </label>
        <input
          id="populi"
          value={populiCode}
          onChange={(e) => setPopuliCode(e.target.value)}
          className="mt-1 w-full rounded border border-zinc-300 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-800"
        />
      </div>
      <button
        type="submit"
        disabled={loading}
        className="rounded bg-zinc-900 px-4 py-2 font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
      >
        {course ? "Update" : "Create"} course
      </button>
    </form>
  );
}
