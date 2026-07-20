import { createBrowserClient } from "@supabase/ssr";

import { getSupabaseConfig, hasSupabaseConfig } from "./config";

export function isSupabaseConfigured(): boolean {
  return hasSupabaseConfig();
}

export function createBrowserSupabase() {
  const config = getSupabaseConfig();
  if (!config) return null;

  return createBrowserClient(config.url, config.anonKey);
}
