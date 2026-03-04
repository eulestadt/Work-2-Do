import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { redirect } from "next/navigation";
import { GeminiConfigForm } from "./gemini-config-form";

export default async function GeminiSettingsPage() {
  const session = await auth();
  if (!session?.user?.id) redirect("/login");

  const config = await prisma.geminiConfig.findUnique({
    where: { userId: session.user.id },
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold">Gemini API key</h1>
      <p className="mt-1 text-zinc-600 dark:text-zinc-400">
        Store your API key to enable syllabus parsing. Keys are encrypted at rest.
      </p>
      <GeminiConfigForm hasConfigured={!!config} />
    </div>
  );
}
