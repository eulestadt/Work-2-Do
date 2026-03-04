import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { writeFile, mkdir } from "fs/promises";
import path from "path";

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.id) return new NextResponse(null, { status: 401 });

  const formData = await req.formData();
  const file = formData.get("file") as File | null;
  const courseId = formData.get("courseId") as string | null;

  if (!file || !courseId) {
    return NextResponse.json({ error: "file and courseId required" }, { status: 400 });
  }

  const course = await prisma.course.findFirst({
    where: { id: courseId, userId: session.user.id },
  });
  if (!course) return new NextResponse(null, { status: 404 });

  const uploadDir = path.join(process.cwd(), "uploads", session.user.id);
  await mkdir(uploadDir, { recursive: true });

  const ext = path.extname(file.name) || ".bin";
  const filename = `${courseId}-${Date.now()}${ext}`;
  const storagePath = path.join(uploadDir, filename);
  const bytes = await file.arrayBuffer();
  await writeFile(storagePath, Buffer.from(bytes));

  const syllabus = await prisma.syllabus.create({
    data: {
      userId: session.user.id,
      courseId,
      storagePath,
      originalFilename: file.name,
      mimeType: file.type || null,
    },
  });

  return NextResponse.json(syllabus);
}
