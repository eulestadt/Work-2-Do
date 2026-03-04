import { NextResponse } from "next/server";
import { resolveUserIdFromApiKey } from "@/lib/app-auth";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { invalidateLatestCache } from "@/lib/latest-cache";

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  let userId: string | null = await resolveUserIdFromApiKey(req);
  if (!userId) {
    const session = await auth();
    userId = session?.user?.id ?? null;
  }
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;

  const assignment = await prisma.assignment.findFirst({
    where: { id, userId },
  });
  if (!assignment) {
    return new NextResponse(null, { status: 404 });
  }

  const completed = !!assignment.completedAt;
  const newCompletedAt = completed ? null : new Date();

  await prisma.assignment.update({
    where: { id },
    data: { completedAt: newCompletedAt },
  });

  invalidateLatestCache(userId);

  return NextResponse.json({ completed: !completed });
}
