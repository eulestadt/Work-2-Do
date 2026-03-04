import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

// Simple XOR "encryption" for dev - replace with proper crypto in production
function encrypt(text: string, key: string): string {
  const result: number[] = [];
  for (let i = 0; i < text.length; i++) {
    result.push(text.charCodeAt(i) ^ key.charCodeAt(i % key.length));
  }
  return Buffer.from(result).toString("base64");
}

function decrypt(encrypted: string, key: string): string {
  const buf = Buffer.from(encrypted, "base64");
  const result: number[] = [];
  for (let i = 0; i < buf.length; i++) {
    result.push(buf[i] ^ key.charCodeAt(i % key.length));
  }
  return String.fromCharCode(...result);
}

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.id) return new NextResponse(null, { status: 401 });

  const { apiKey } = await req.json();
  if (!apiKey) return NextResponse.json({ error: "API key required" }, { status: 400 });

  const secret = process.env.APP_ENCRYPTION_KEY ?? "dev-secret-change-in-production";
  const encrypted = encrypt(apiKey, secret);

  await prisma.geminiConfig.upsert({
    where: { userId: session.user.id },
    create: {
      userId: session.user.id,
      encryptedApiKey: encrypted,
    },
    update: { encryptedApiKey: encrypted },
  });

  return NextResponse.json({ ok: true });
}
