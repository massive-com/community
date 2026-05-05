export function PanelError({
  message,
  compact = false,
}: {
  message: string;
  compact?: boolean;
}) {
  return (
    <div
      className={`rounded border border-rose-500/30 bg-rose-500/10 font-mono text-rose-200 ${
        compact ? "px-2 py-1 text-[10px]" : "px-3 py-2 text-[11px]"
      }`}
    >
      {message}
    </div>
  );
}
