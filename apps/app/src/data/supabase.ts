import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

/** Supabase is used for sign-in and Realtime only. Null until the project keys are in .env (dev uses personas). */
export const supabaseConfigured = !!URL && !!KEY;

let client: SupabaseClient | null = null;
export function getSupabase(): SupabaseClient | null {
  if (!supabaseConfigured) return null;
  client ??= createClient(URL, KEY, { auth: { flowType: "pkce", detectSessionInUrl: true, persistSession: true } });
  return client;
}
