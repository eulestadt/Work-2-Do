import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { decryptApiKey, parseSyllabusWithGemini } from "@/lib/gemini";
import { readFile } from "fs/promises";
import path from "path";
import { PDFParse } from "pdf-parse";

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.id) return new NextResponse(null, { status: 401 });

  const { syllabusId } = await req.json();
  if (!syllabusId) return NextResponse.json({ error: "syllabusId required" }, { status: 400 });

  const syllabus = await prisma.syllabus.findFirst({
    where: { id: syllabusId, userId: session.user.id },
    include: { course: true },
  });
  if (!syllabus) return new NextResponse(null, { status: 404 });

  const config = await prisma.geminiConfig.findUnique({
    where: { userId: session.user.id },
  });
  if (!config) {
    return NextResponse.json({ error: "Gemini API key not configured" }, { status: 400 });
  }

  try {
    const apiKey = decryptApiKey(config.encryptedApiKey);
    const buf = await readFile(syllabus.storagePath);
    const ext = path.extname(syllabus.originalFilename).toLowerCase();

    let text: string;
    if (ext === ".pdf") {
      const parser = new PDFParse({ data: buf });
      const result = await parser.getText();
      text = result.text;
      await parser.destroy();
    } else {
      text = buf.toString("utf-8");
    }

    const items = await parseSyllabusWithGemini(apiKey, text, syllabus.course.title);

    for (const item of items) {
      await prisma.assignment.create({
        data: {
          userId: session.user.id,
          courseId: syllabus.courseId,
          title: item.title,
          type: item.type || "other",
          description: item.description ?? null,
          dueDate: item.dueDate ? new Date(item.dueDate) : null,
          estimatedTimeMinutes: item.estimatedTimeMinutes ?? null,
          source: "ai_parsed",
        },
      });
    }

    await prisma.syllabus.update({
      where: { id: syllabusId },
      data: { uploadStatus: "parsed" },
    });

    return NextResponse.json({ ok: true, count: items.length });
  } catch (e) {
    console.error("Syllabus parse error:", e);
    await prisma.syllabus.update({
      where: { id: syllabusId },
      data: { uploadStatus: "error" },
    });
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Parse failed" },
      { status: 500 }
    );
  }
}
