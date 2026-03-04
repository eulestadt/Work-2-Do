import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { redirect } from "next/navigation";
import { AssignmentForm } from "../assignment-form";

export default async function NewAssignmentPage({
  searchParams,
}: {
  searchParams: Promise<{ course?: string }>;
}) {
  const session = await auth();
  if (!session?.user?.id) redirect("/login");

  const { course: courseId } = await searchParams;
  const courses = await prisma.course.findMany({
    where: { userId: session.user.id },
    orderBy: { title: "asc" },
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold">Add assignment</h1>
      <AssignmentForm userId={session.user.id} courses={courses} defaultCourseId={courseId ?? undefined} />
    </div>
  );
}
