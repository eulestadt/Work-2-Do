import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { CourseForm } from "../course-form";

export default async function NewCoursePage() {
  const session = await auth();
  if (!session?.user?.id) redirect("/login");

  return (
    <div>
      <h1 className="text-2xl font-semibold">Add course</h1>
      <CourseForm userId={session.user.id} />
    </div>
  );
}
