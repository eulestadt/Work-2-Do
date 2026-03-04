import { NextResponse } from "next/server";
import { resolveUserIdFromApiKey } from "@/lib/app-auth";
import { prisma } from "@/lib/prisma";
import { checkRateLimit } from "@/lib/rate-limit";
import { decryptApiKey, askGeminiAboutSchedule } from "@/lib/gemini";

export async function POST(req: Request) {
  const userId = await resolveUserIdFromApiKey(req);
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: { question?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const question = body.question?.trim();
  if (!question) {
    return NextResponse.json({ error: "Missing or empty 'question' in request body" }, { status: 400 });
  }

  if (!checkRateLimit(userId)) {
    return NextResponse.json({ error: "Rate limit exceeded" }, { status: 429 });
  }

  const config = await prisma.geminiConfig.findUnique({
    where: { userId },
  });
  if (!config) {
    return NextResponse.json(
      { error: "Gemini API key not configured. Add it in Settings." },
      { status: 400 }
    );
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const weekEnd = new Date(today);
  weekEnd.setDate(weekEnd.getDate() + 14);

  const assignments = await prisma.assignment.findMany({
    where: { userId, dueDate: { gte: today, lte: weekEnd } },
    include: { course: true },
    orderBy: { dueDate: "asc" },
  });

  const digestMd = assignments
    .map((a) => `- ${a.title} (${a.course.title})${a.dueDate ? ` due ${a.dueDate.toISOString().slice(0, 10)}` : ""}`)
    .join("\n");
  const contextSummary = assignments.map((a) => a.title).join(", ") || "No assignments.";

  try {
    const apiKey = decryptApiKey(config.encryptedApiKey);
    const answer = await askGeminiAboutSchedule(
      apiKey,
      question,
      contextSummary,
      digestMd,
      digestMd
    );
    return NextResponse.json({ answer });
  } catch (e) {
    console.error("ask_gemini failed:", e);
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Gemini request failed" },
      { status: 503 }
    );
  }
}
