// Shown over the heatmap while a new snapshot is being fetched. The canvas behind
// it is dimmed and blurred (via the `.is-loading` class on .canvas-wrap) so the
// previous view stays as context instead of flashing to black.
export function LoadingOverlay({ name }: { name?: string }) {
  return (
    <div className="loading-overlay">
      <div className="spinner" />
      <div className="loading-label">{name ? `Loading ${name}…` : "Loading…"}</div>
    </div>
  );
}
