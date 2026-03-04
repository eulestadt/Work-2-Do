import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import Link from "next/link";

export default async function DashboardPage() {
  const session = await auth();
  if (!session?.user?.id) return null;

  const [courses, assignments, nextDue] = await Promise.all([
    prisma.course.findMany({
      where: { userId: session.user.id },
      include: { _count: { select: { assignments: true } } },
    }),
    prisma.assignment.findMany({
      where: { userId: session.user.id },
      include: { course: true },
      orderBy: { dueDate: "asc" },
      take: 10,
    }),
    prisma.assignment.findFirst({
      where: {
        userId: session.user.id,
        dueDate: { gte: new Date() },
      },
      include: { course: true },
      orderBy: { dueDate: "asc" },
    }),
  ]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="mt-1 text-zinc-600 dark:text-zinc-400">
          Welcome back. Manage your courses and assignments.
        </p>
      </div>

      {nextDue && (
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Next due</h2>
          <p className="mt-1 font-medium">{nextDue.title}</p>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            {nextDue.course.title} · {nextDue.dueDate?.toLocaleDateString()}
          </p>
        </div>
      )}

      <div>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Courses</h2>
          <Link
            href="/courses/new"
            className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
          >
            Add course
          </Link>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {courses.length === 0 ? (
            <p className="col-span-2 text-zinc-600 dark:text-zinc-400">
              No courses yet. Add a course to get started.
            </p>
          ) : (
            courses.map((c) => (
              <Link
                key={c.id}
                href={`/courses/${c.id}`}
                className="rounded-lg border border-zinc-200 bg-white p-4 hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700"
              >
                <h3 className="font-medium">{c.title}</h3>
                <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                  {c._count.assignments} assignments
                </p>
              </Link>
            ))
          )}
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold">Recent assignments</h2>
        <div className="mt-4 space-y-2">
          {assignments.length === 0 ? (
            <p className="text-zinc-600 dark:text-zinc-400">No assignments yet.</p>
          ) : (
            assignments.map((a) => (
              <Link
                key={a.id}
                href={`/assignments?course=${a.courseId}`}
                className="block rounded border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900"
              >
                <span className="font-medium">{a.title}</span>
                <span className="ml-2 text-sm text-zinc-600 dark:text-zinc-400">
                  {a.course.title} · {a.dueDate?.toLocaleDateString() ?? "No date"}
                </span>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
