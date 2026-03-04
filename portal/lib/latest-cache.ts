export type LatestResponse = {
  date: string;
  digest_md: string;
  gameplan_md: string;
  gameplan_tomorrow_md: string;
  items: Array<{
    id: string;
    course: string;
    date: string;
    type: string;
    title: string;
    description: string;
    url: string;
    is_major: boolean;
    completed: boolean;
  }>;
  context_summary_7_14: string;
};

const CACHE_TTL_MS = 15 * 60 * 1000; // 15 minutes
const cache = new Map<string, { data: LatestResponse; expires: number }>();

export function getCachedLatest(userId: string): LatestResponse | null {
  const entry = cache.get(userId);
  if (!entry || Date.now() >= entry.expires) return null;
  return entry.data;
}

export function setCachedLatest(userId: string, data: LatestResponse) {
  cache.set(userId, { data, expires: Date.now() + CACHE_TTL_MS });
}

export function invalidateLatestCache(userId: string) {
  cache.delete(userId);
}
