import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import Link from "next/link";

export default async function Home() {
  const session = await auth();
  if (session?.user) redirect("/dashboard");

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50 dark:bg-zinc-950">
      <h1 className="text-2xl font-semibold">Homework Portal</h1>
      <p className="mt-2 text-zinc-600 dark:text-zinc-400">
        Manage courses, syllabi, and assignments.
      </p>
      <div className="mt-6 flex gap-4">
        <Link
          href="/login"
          className="rounded bg-zinc-900 px-6 py-2 font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
        >
          Sign in
        </Link>
        <Link
          href="/register"
          className="rounded border border-zinc-300 px-6 py-2 font-medium hover:bg-zinc-100 dark:border-zinc-600 dark:hover:bg-zinc-800"
        >
          Register
        </Link>
      </div>
    </div>
  );
}
