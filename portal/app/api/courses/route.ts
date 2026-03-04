import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) return new NextResponse(null, { status: 401 });

  const courses = await prisma.course.findMany({
    where: { userId: session.user.id },
    orderBy: { title: "asc" },
  });
  return NextResponse.json(courses);
}

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.id) return new NextResponse(null, { status: 401 });

  const { title, term, populiCourseCode } = await req.json();
  if (!title) return NextResponse.json({ error: "Title required" }, { status: 400 });

  const course = await prisma.course.create({
    data: {
      userId: session.user.id,
      title,
      term: term || null,
      populiCourseCode: populiCourseCode || null,
    },
  });
  return NextResponse.json(course);
}
