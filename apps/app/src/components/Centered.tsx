/** A single centred column for full-screen states outside the tabs (loading, errors). */
export function Centered({ children }: { children: React.ReactNode }) {
  return <main className="mx-auto flex min-h-dvh w-full max-w-[440px] flex-col justify-center gap-4 px-4 py-12">{children}</main>;
}
