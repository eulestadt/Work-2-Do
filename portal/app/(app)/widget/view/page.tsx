import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { redirect } from "next/navigation";

export default async function WidgetViewPage() {
  const session = await auth();
  if (!session?.user?.id) redirect("/login");

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  const assignments = await prisma.assignment.findMany({
    where: {
      userId: session.user.id,
      dueDate: { gte: today, lt: tomorrow },
    },
    include: { course: true },
    orderBy: { dueDate: "asc" },
  });

  return (
    <div className="min-h-screen bg-zinc-950 text-white p-6 font-sans">
      <h1 className="text-lg font-semibold text-zinc-400 mb-4">Today</h1>
      {assignments.length === 0 ? (
        <p className="text-zinc-500">No assignments due today.</p>
      ) : (
        <ul className="space-y-3">
          {assignments.map((a) => (
            <li key={a.id} className="flex flex-col">
              <span className="font-medium">{a.title}</span>
              <span className="text-sm text-zinc-600">{a.course.title}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
