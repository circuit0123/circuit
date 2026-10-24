"use client";

import { ToastProvider } from "@circuit/ui";
import { DataProvider, useApplyAppearance } from "@/data";

function Appearance() {
  useApplyAppearance();
  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <DataProvider>
      <Appearance />
      <ToastProvider>{children}</ToastProvider>
    </DataProvider>
  );
}
