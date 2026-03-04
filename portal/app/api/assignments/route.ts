import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user?.id) return new NextResponse(null, { status: 401 });

  const { searchParams } = new URL(req.url);
  const courseId = searchParams.get("course");

  const where: { userId: string; courseId?: string } = { userId: session.user.id };
  if (courseId) where.courseId = courseId;

  const assignments = await prisma.assignment.findMany({
    where,
    include: { course: true },
    orderBy: { dueDate: "asc" },
  });
  return NextResponse.json(assignments);
}

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.id) return new NextResponse(null, { status: 401 });

  const { courseId, title, type, description, dueDate, estimatedTimeMinutes } = await req.json();
  if (!courseId || !title) {
    return NextResponse.json({ error: "courseId and title required" }, { status: 400 });
  }

  const course = await prisma.course.findFirst({
    where: { id: courseId, userId: session.user.id },
  });
  if (!course) return new NextResponse(null, { status: 404 });

  const assignment = await prisma.assignment.create({
    data: {
      userId: session.user.id,
      courseId,
      title,
      type: type || "other",
      description: description || null,
      dueDate: dueDate ? new Date(dueDate) : null,
      estimatedTimeMinutes: estimatedTimeMinutes ?? null,
    },
  });
  return NextResponse.json(assignment);
}
