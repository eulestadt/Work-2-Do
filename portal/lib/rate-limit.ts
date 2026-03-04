const windowMs = 60 * 1000; // 1 minute
const maxPerWindow = 30; // 30 requests per minute per user
const store = new Map<string, { count: number; resetAt: number }>();

export function checkRateLimit(userId: string): boolean {
  const now = Date.now();
  const entry = store.get(userId);
  if (!entry) {
    store.set(userId, { count: 1, resetAt: now + windowMs });
    return true;
  }
  if (now > entry.resetAt) {
    store.set(userId, { count: 1, resetAt: now + windowMs });
    return true;
  }
  entry.count++;
  return entry.count <= maxPerWindow;
}
