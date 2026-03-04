import { prisma } from "./prisma";
import { createHash, randomBytes } from "crypto";

export function hashKey(key: string): string {
  return createHash("sha256").update(key).digest("hex");
}

export async function resolveUserIdFromApiKey(request: Request): Promise<string | null> {
  const authHeader = request.headers.get("authorization");
  const apiKeyHeader = request.headers.get("x-api-key");
  const rawKey = authHeader?.startsWith("Bearer ")
    ? authHeader.slice(7)
    : apiKeyHeader?.trim();

  if (!rawKey) return null;

  const keyHash = hashKey(rawKey);
  const appKey = await prisma.appApiKey.findFirst({
    where: { keyHash },
    select: { userId: true },
  });
  return appKey?.userId ?? null;
}

export function generateApiKey(): string {
  return randomBytes(32).toString("hex");
}
