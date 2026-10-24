import { useSession } from "./session";

/** Query keys carry no token. The cache is cleared whenever someone signs in or out (SessionProvider), so one person's data is never shown to another. */
export function useKey(...k: unknown[]) {
  const { token } = useSession();
  return { key: k, enabled: !!token, token };
}
