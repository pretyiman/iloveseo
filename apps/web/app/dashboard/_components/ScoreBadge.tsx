function bandFor(score: number): { bg: string; text: string; border: string } {
  if (score >= 90) return { bg: "bg-green-950", text: "text-green-300", border: "border-green-800" };
  if (score >= 70) return { bg: "bg-lime-950", text: "text-lime-300", border: "border-lime-800" };
  if (score >= 50) return { bg: "bg-orange-950", text: "text-orange-300", border: "border-orange-800" };
  return { bg: "bg-red-950", text: "text-red-300", border: "border-red-800" };
}

export function ScoreBadge({ score, size = "md" }: { score: number | null; size?: "sm" | "md" }) {
  const dims = size === "sm" ? "h-8 w-8 text-xs" : "h-11 w-11 text-sm";

  if (score === null) {
    return (
      <div
        className={`flex ${dims} shrink-0 items-center justify-center rounded-full border border-neutral-700 bg-neutral-900 font-medium text-neutral-500`}
      >
        --
      </div>
    );
  }

  const { bg, text, border } = bandFor(score);
  return (
    <div
      className={`flex ${dims} shrink-0 items-center justify-center rounded-full border ${border} ${bg} ${text} font-semibold`}
    >
      {score}
    </div>
  );
}
