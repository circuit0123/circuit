import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema";

export type { components, paths };
export type Schemas = components["schemas"];

/** The one error shape every backend failure uses: {error: {code, message, details}}. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type ApiOptions = {
  baseUrl: string;
  /** Returns the bearer token (Supabase session or demo token), or null when signed out. */
  getToken: () => Promise<string | null> | string | null;
};

export function createApi({ baseUrl, getToken }: ApiOptions) {
  const client = createClient<paths>({ baseUrl });
  const auth: Middleware = {
    async onRequest({ request }) {
      const token = await getToken();
      if (token) request.headers.set("Authorization", `Bearer ${token}`);
      return request;
    },
  };
  client.use(auth);
  return client;
}

export type Api = ReturnType<typeof createApi>;

/**
 * Unwraps an openapi-fetch result: returns the data, or throws ApiError built from the
 * standard error envelope. Every hook calls the API through this, so errors look the same.
 */
export async function unwrap<T>(
  result: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let r;
  try {
    r = await result;
  } catch {
    throw new ApiError(0, "network", "Can't reach Circuit. Check your connection and try again.");
  }
  if (r.error !== undefined || r.data === undefined) {
    const env = (r.error as { error?: { code?: string; message?: string; details?: unknown } } | undefined)?.error;
    if (r.response.status === 204 || (r.response.ok && r.error === undefined)) return undefined as T;
    throw new ApiError(
      r.response.status,
      env?.code ?? "unknown",
      env?.message ?? "Something went wrong. Try again.",
      env?.details,
    );
  }
  return r.data;
}
