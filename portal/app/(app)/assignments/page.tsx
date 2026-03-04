import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import Link from "next/link";
import { AssignmentToggle } from "./assignment-toggle";

export default async function AssignmentsPage({
  searchParams,
}: {
  searchParams: Promise<{ course?: string }>;
}) {
  const session = await auth();
  if (!session?.user?.id) return null;

  const { course: courseId } = await searchParams;

  const where: { userId: string; courseId?: string } = { userId: session.user.id };
  if (courseId) where.courseId = courseId;

  const [assignments, courses] = await Promise.all([
    prisma.assignment.findMany({
      where,
      include: { course: true },
      orderBy: { dueDate: "asc" },
    }),
    prisma.course.findMany({
      where: { userId: session.user.id },
      orderBy: { title: "asc" },
    }),
  ]);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Assignments</h1>
        <Link
          href="/assignments/new"
          className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
        >
          Add assignment
        </Link>
      </div>

      <div className="flex gap-2">
        <Link
          href="/assignments"
          className={`rounded px-3 py-1 text-sm ${!courseId ? "bg-zinc-200 dark:bg-zinc-700" : "bg-zinc-100 dark:bg-zinc-800"}`}
        >
          All
        </Link>
        {courses.map((c) => (
          <Link
            key={c.id}
            href={`/assignments?course=${c.id}`}
            className={`rounded px-3 py-1 text-sm ${courseId === c.id ? "bg-zinc-200 dark:bg-zinc-700" : "bg-zinc-100 dark:bg-zinc-800"}`}
          >
            {c.title}
          </Link>
        ))}
      </div>

      <div className="space-y-2">
        {assignments.length === 0 ? (
          <p className="text-zinc-600 dark:text-zinc-400">No assignments.</p>
        ) : (
          assignments.map((a) => (
            <div
              key={a.id}
              className="rounded border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <AssignmentToggle id={a.id} completed={!!a.completedAt}>
                <h3 className="font-medium">{a.title}</h3>
                <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                  {a.course.title} · {a.type} · {a.dueDate?.toLocaleDateString() ?? "No date"}
                </p>
                {a.description && (
                  <p className="mt-2 text-sm text-zinc-500">{a.description}</p>
                )}
              </AssignmentToggle>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
