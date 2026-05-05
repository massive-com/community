interface SkeletonProps {
  className?: string;
  width?: string | number;
  height?: string | number;
}

/** Inline shimmering placeholder for loading data. */
export function Skeleton({ className = "", width, height }: SkeletonProps) {
  const style: React.CSSProperties = {};
  if (width !== undefined) style.width = width;
  if (height !== undefined) style.height = height;
  return (
    <span
      className={`inline-block align-middle bg-bg-edge/60 rounded animate-pulse ${className}`}
      style={style}
    />
  );
}

/** Block-level loading panel. */
export function PanelLoading({
  message = "loading...",
  className = "",
}: {
  message?: string;
  className?: string;
}) {
  return (
    <div
      className={`flex items-center justify-center text-[11px] font-mono text-zinc-500 gap-2 ${className}`}
    >
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-blue animate-pulse" />
      {message}
    </div>
  );
}
