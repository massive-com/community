"use client";

interface Props {
  values: number[];
  width?: number;
  height?: number;
  positive?: boolean;
}

export function Sparkline({ values, width = 80, height = 22, positive }: Props) {
  if (!values || values.length < 2) {
    return <div style={{ width, height }} className="opacity-30" />;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = width / (values.length - 1);

  const points = values
    .map((v, i) => `${(i * stepX).toFixed(2)},${(height - ((v - min) / range) * height).toFixed(2)}`)
    .join(" ");

  const stroke =
    positive === undefined
      ? "#9ca3af"
      : positive
        ? "#22c55e"
        : "#ef4444";

  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth={1.4}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
