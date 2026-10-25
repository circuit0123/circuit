"use client";

import { ThemeProvider, ToastProvider } from "@circuit/ui";
import { DataProvider, useAppearance } from "@/data";

/** Theme and accent from the member's saved appearance. Until it is known, the first-paint script's colours stay. */
function Theme({ children }: { children: React.ReactNode }) {
  const { appearance } = useAppearance();
  return <ThemeProvider theme={appearance?.theme} accent={appearance?.accent}>{children}</ThemeProvider>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <DataProvider>
      <Theme>
        <ToastProvider>{children}</ToastProvider>
      </Theme>
    </DataProvider>
  );
}
