import { NextResponse } from "next/server";
import { resolveUserIdFromApiKey } from "@/lib/app-auth";
import { prisma } from "@/lib/prisma";
import { checkRateLimit } from "@/lib/rate-limit";
import { decryptApiKey } from "@/lib/gemini";
import {
  generateGameplanWithGemini,
  generateContextSummaryWithGemini,
  type AssignmentForGameplan,
} from "@/lib/gemini";
import {
  getCachedLatest,
  setCachedLatest,
  type LatestResponse,
} from "@/lib/latest-cache";

function toDateStr(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export async function GET(req: Request) {
  const userId = await resolveUserIdFromApiKey(req);
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  if (!checkRateLimit(userId)) {
    return NextResponse.json({ error: "Rate limit exceeded" }, { status: 429 });
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const weekEnd = new Date(today);
  weekEnd.setDate(weekEnd.getDate() + 14);

  const cached = getCachedLatest(userId);
  if (cached) {
    return NextResponse.json(cached);
  }

  const assignments = await prisma.assignment.findMany({
    where: {
      userId,
      dueDate: { gte: today, lte: weekEnd },
    },
    include: { course: true },
    orderBy: { dueDate: "asc" },
  });

  const todayStr = toDateStr(today);
  const tomorrowStr = toDateStr(tomorrow);

  const items: LatestResponse["items"] = assignments.map((a) => ({
    id: a.id,
    course: a.course.title,
    date: a.dueDate ? toDateStr(a.dueDate) : "",
    type: a.type,
    title: a.title,
    description: a.description ?? "",
    url: "",
    is_major: a.type === "exam" || a.type === "project",
    completed: !!a.completedAt,
  }));

  const forGameplan: AssignmentForGameplan[] = assignments.map((a) => ({
    title: a.title,
    type: a.type,
    dueDate: a.dueDate,
    courseTitle: a.course.title,
    completed: !!a.completedAt,
  }));

  const todayItems = forGameplan.filter(
    (a) => a.dueDate && toDateStr(a.dueDate) === todayStr
  );
  const tomorrowItems = forGameplan.filter(
    (a) => a.dueDate && toDateStr(a.dueDate) === tomorrowStr
  );

  let digest_md = "";
  let gameplan_md = "";
  let gameplan_tomorrow_md = "";
  let context_summary_7_14 = "";

  const config = await prisma.geminiConfig.findUnique({
    where: { userId },
  });

  if (config) {
    try {
      const apiKey = decryptApiKey(config.encryptedApiKey);
      [gameplan_md, gameplan_tomorrow_md, context_summary_7_14] = await Promise.all([
        generateGameplanWithGemini(apiKey, todayItems, "today"),
        generateGameplanWithGemini(apiKey, tomorrowItems, "tomorrow"),
        generateContextSummaryWithGemini(apiKey, forGameplan),
      ]);
      digest_md = `# Today\n\n${gameplan_md}\n\n# Tomorrow\n\n${gameplan_tomorrow_md}`;
    } catch (e) {
      console.error("Gameplan generation failed:", e);
      digest_md = items.length
        ? `# Assignments\n\n${items.map((i) => `- ${i.title} (${i.course})`).join("\n")}`
        : "No assignments.";
      gameplan_md = digest_md;
      context_summary_7_14 = items.map((i) => i.title).join(", ") || "No assignments.";
    }
  } else {
    digest_md = items.length
      ? `# Assignments\n\n${items.map((i) => `- ${i.title} (${i.course})`).join("\n")}`
      : "No assignments. Add your Gemini API key in Settings to generate gameplans.";
    gameplan_md = digest_md;
    gameplan_tomorrow_md = "";
    context_summary_7_14 = items.map((i) => i.title).join(", ") || "No assignments.";
  }

  const data: LatestResponse = {
    date: todayStr,
    digest_md,
    gameplan_md,
    gameplan_tomorrow_md,
    items,
    context_summary_7_14,
  };

  setCachedLatest(userId, data);

  return NextResponse.json(data);
}
