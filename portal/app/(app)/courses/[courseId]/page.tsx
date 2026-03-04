import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { redirect, notFound } from "next/navigation";
import Link from "next/link";
import { CourseForm } from "../course-form";
import { SyllabusUpload } from "./syllabus-upload";
import { SyllabusParseButton } from "./syllabus-parse-button";
import { AssignmentToggle } from "../../assignments/assignment-toggle";

export default async function CoursePage({ params }: { params: Promise<{ courseId: string }> }) {
  const { courseId } = await params;
  const session = await auth();
  if (!session?.user?.id) redirect("/login");

  const course = await prisma.course.findFirst({
    where: { id: courseId, userId: session.user.id },
    include: { assignments: { orderBy: { dueDate: "asc" } }, syllabi: true },
  });

  if (!course) notFound();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">{course.title}</h1>
        <CourseForm userId={session.user.id} course={course} />
      </div>

      <div>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Assignments</h2>
          <Link
            href={`/assignments/new?course=${courseId}`}
            className="text-sm font-medium text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
          >
            Add assignment
          </Link>
        </div>
        <div className="mt-4 space-y-2">
          {course.assignments.length === 0 ? (
            <p className="text-zinc-600 dark:text-zinc-400">No assignments yet.</p>
          ) : (
            course.assignments.map((a) => (
              <div
                key={a.id}
                className="rounded border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900"
              >
                <AssignmentToggle id={a.id} completed={!!a.completedAt}>
                  <Link href={`/assignments?course=${courseId}`} className="font-medium hover:underline">
                    {a.title}
                  </Link>
                  <span className="ml-2 text-sm text-zinc-600 dark:text-zinc-400">
                    {a.type} · {a.dueDate?.toLocaleDateString() ?? "No date"}
                  </span>
                </AssignmentToggle>
              </div>
            ))
          )}
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold">Syllabi</h2>
        <SyllabusUpload courseId={courseId} />
        <div className="mt-4 space-y-2">
          {course.syllabi.length === 0 ? (
            <p className="text-zinc-600 dark:text-zinc-400">No syllabi uploaded yet.</p>
          ) : (
            course.syllabi.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between rounded border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900"
              >
                <span>{s.originalFilename}</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-zinc-500">{s.uploadStatus}</span>
                  {s.uploadStatus === "uploaded" && (
                    <SyllabusParseButton syllabusId={s.id} />
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
