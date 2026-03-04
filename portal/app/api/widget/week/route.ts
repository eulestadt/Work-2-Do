import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user?.id) return new NextResponse(null, { status: 401 });

  const now = new Date();
  const weekEnd = new Date(now);
  weekEnd.setDate(weekEnd.getDate() + 7);

  const assignments = await prisma.assignment.findMany({
    where: {
      userId: session.user.id,
      dueDate: { gte: now, lte: weekEnd },
    },
    include: { course: true },
    orderBy: { dueDate: "asc" },
  });

  const items = assignments.map((a) => ({
    id: a.id,
    title: a.title,
    courseTitle: a.course.title,
    dueDate: a.dueDate?.toISOString() ?? null,
    remainingMinutes: a.estimatedTimeMinutes,
    type: a.type,
  }));

  return NextResponse.json({ items });
}
