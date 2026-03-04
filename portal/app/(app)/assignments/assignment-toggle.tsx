"use client";

import { useRouter } from "next/navigation";

export function AssignmentToggle({
  id,
  completed,
  children,
}: {
  id: string;
  completed: boolean;
  children: React.ReactNode;
}) {
  const router = useRouter();

  const toggle = async () => {
    const res = await fetch(`/api/assignments/${id}/complete`, {
      method: "POST",
    });
    if (res.ok) {
      router.refresh();
    }
  };

  return (
    <div className="flex items-start gap-3">
      <button
        type="button"
        onClick={toggle}
        className="mt-0.5 shrink-0 rounded p-0.5 hover:bg-zinc-100 dark:hover:bg-zinc-800"
        aria-label={completed ? "Mark incomplete" : "Mark complete"}
      >
        {completed ? (
          <span className="text-green-600 dark:text-green-400">✓</span>
        ) : (
          <span className="text-zinc-400 dark:text-zinc-500">○</span>
        )}
      </button>
      <div className={completed ? "text-zinc-500 line-through dark:text-zinc-400" : ""}>
        {children}
      </div>
    </div>
  );
}
