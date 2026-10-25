/** A labelled sample: "Example" for something we wrote to show what a screen is like, "Demo data" for a real screen filled with demo data. Never passed off as real. */
export function Example({ label = "Example", className, children }: { label?: "Example" | "Demo data"; className?: string; children: React.ReactNode }) {
  return (
    <div className={`rounded-card bg-surface p-surface ${className ?? ""}`}>
      <p className="mb-4 inline-block rounded-full bg-surface-2 px-3 py-1 t-subhead text-text">{label}</p>
      {children}
    </div>
  );
}
