import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ courseId: string }> }
) {
  const session = await auth();
  if (!session?.user?.id) return new NextResponse(null, { status: 401 });

  const course = await prisma.course.findFirst({
    where: { id: (await params).courseId, userId: session.user.id },
    include: { assignments: true, syllabi: true },
  });
  if (!course) return new NextResponse(null, { status: 404 });
  return NextResponse.json(course);
}

export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ courseId: string }> }
) {
  const session = await auth();
  if (!session?.user?.id) return new NextResponse(null, { status: 401 });

  const courseId = (await params).courseId;
  const existing = await prisma.course.findFirst({
    where: { id: courseId, userId: session.user.id },
  });
  if (!existing) return new NextResponse(null, { status: 404 });

  const { title, term, populiCourseCode } = await req.json();
  const course = await prisma.course.update({
    where: { id: courseId },
    data: {
      ...(title != null && { title }),
      ...(term != null && { term }),
      ...(populiCourseCode != null && { populiCourseCode }),
    },
  });
  return NextResponse.json(course);
}

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ courseId: string }> }
) {
  const session = await auth();
  if (!session?.user?.id) return new NextResponse(null, { status: 401 });

  const courseId = (await params).courseId;
  const existing = await prisma.course.findFirst({
    where: { id: courseId, userId: session.user.id },
  });
  if (!existing) return new NextResponse(null, { status: 404 });

  await prisma.course.delete({ where: { id: courseId } });
  return new NextResponse(null, { status: 204 });
}
