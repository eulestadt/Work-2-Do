import { GoogleGenerativeAI } from "@google/generative-ai";

function getDecrypt(encrypted: string, key: string): string {
  const buf = Buffer.from(encrypted, "base64");
  const result: number[] = [];
  for (let i = 0; i < buf.length; i++) {
    result.push(buf[i] ^ key.charCodeAt(i % key.length));
  }
  return String.fromCharCode(...result);
}

export function decryptApiKey(encrypted: string): string {
  const secret = process.env.APP_ENCRYPTION_KEY ?? "dev-secret-change-in-production";
  return getDecrypt(encrypted, secret);
}

export async function parseSyllabusWithGemini(
  apiKey: string,
  text: string,
  courseTitle: string
): Promise<Array<{ title: string; type: string; dueDate?: string; description?: string; estimatedTimeMinutes?: number }>> {
  const genAI = new GoogleGenerativeAI(apiKey);
  const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash" });

  const prompt = `Extract all assignments, readings, exams, and due dates from this syllabus. Return a JSON array of objects with: title (string), type (one of: reading, homework, exam, project, other), dueDate (ISO date string or null), description (string or null), estimatedTimeMinutes (number or null). Course: ${courseTitle}

Syllabus text:
---
${text.slice(0, 30000)}
---

Return ONLY valid JSON array, no markdown or extra text.`;

  const result = await model.generateContent(prompt);
  const response = result.response;
  const raw = response.text();
  const jsonMatch = raw.match(/\[[\s\S]*\]/);
  const jsonStr = jsonMatch ? jsonMatch[0] : raw;
  const parsed = JSON.parse(jsonStr) as Array<{ title: string; type: string; dueDate?: string; description?: string; estimatedTimeMinutes?: number }>;
  return Array.isArray(parsed) ? parsed : [];
}

export type AssignmentForGameplan = {
  title: string;
  type: string;
  dueDate: Date | null;
  courseTitle: string;
  completed: boolean;
};

export async function generateGameplanWithGemini(
  apiKey: string,
  assignments: AssignmentForGameplan[],
  dateLabel: string
): Promise<string> {
  const genAI = new GoogleGenerativeAI(apiKey);
  const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash" });

  const list = assignments
    .map(
      (a) =>
        `- [${a.completed ? "x" : " "}] ${a.title} (${a.courseTitle}, ${a.type})${a.dueDate ? ` due ${a.dueDate.toISOString().slice(0, 10)}` : ""}`
    )
    .join("\n");

  const prompt = `Given these assignments for ${dateLabel}, produce a concise markdown gameplan (headers, bullet points, priorities). Use ### for section headers. Be practical and actionable.

Assignments:
${list || "(none)"}

Return ONLY the markdown, no preamble.`;

  const result = await model.generateContent(prompt);
  return result.response.text()?.trim() ?? "";
}

export async function generateContextSummaryWithGemini(
  apiKey: string,
  assignments: AssignmentForGameplan[]
): Promise<string> {
  const genAI = new GoogleGenerativeAI(apiKey);
  const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash" });

  const list = assignments
    .map(
      (a) =>
        `- ${a.title} (${a.courseTitle})${a.dueDate ? ` due ${a.dueDate.toISOString().slice(0, 10)}` : ""}`
    )
    .join("\n");

  const prompt = `Summarize the next 7-14 days of assignments in 2-4 sentences for use as context in a Q&A system. Be concise.

Assignments:
${list || "(none)"}

Return plain text only.`;

  const result = await model.generateContent(prompt);
  return result.response.text()?.trim() ?? "";
}

export async function askGeminiAboutSchedule(
  apiKey: string,
  question: string,
  contextSummary: string,
  gameplanMd: string,
  digestMd: string
): Promise<string> {
  const genAI = new GoogleGenerativeAI(apiKey);
  const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash" });

  const prompt = `You are a helpful assistant for a student's homework schedule. Answer the question using ONLY the context below. If the context doesn't contain enough information, say so. Be concise.

Context summary: ${contextSummary}

Digest:
${digestMd}

Gameplan:
${gameplanMd}

User question: ${question}

Answer (use only information from the schedule context above):`;

  const result = await model.generateContent(prompt);
  return result.response.text()?.trim() ?? "";
}
