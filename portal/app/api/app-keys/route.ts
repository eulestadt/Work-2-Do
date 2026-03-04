import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { generateApiKey, hashKey } from "@/lib/app-auth";

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) return new NextResponse(null, { status: 401 });

  const keys = await prisma.appApiKey.findMany({
    where: { userId: session.user.id },
    select: { id: true, label: true, createdAt: true },
    orderBy: { createdAt: "desc" },
  });

  return NextResponse.json({ keys });
}

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.id) return new NextResponse(null, { status: 401 });

  const body = await req.json().catch(() => ({}));
  const label = body.label?.trim() || null;

  const rawKey = generateApiKey();
  const keyHash = hashKey(rawKey);

  await prisma.appApiKey.create({
    data: {
      userId: session.user.id,
      keyHash,
      label,
    },
  });

  return NextResponse.json({
    key: rawKey,
    message: "Copy this key now. It will not be shown again.",
  });
}
