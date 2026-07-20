export interface SupabaseEnv extends Record<string, string | undefined> {
  NEXT_PUBLIC_SUPABASE_URL?: string;
  NEXT_PUBLIC_SUPABASE_ANON_KEY?: string;
}

export function hasSupabaseConfig(env: SupabaseEnv = process.env): boolean {
  return Boolean(env.NEXT_PUBLIC_SUPABASE_URL && env.NEXT_PUBLIC_SUPABASE_ANON_KEY);
}

export function getSupabaseConfig(env: SupabaseEnv = process.env): {
  url: string;
  anonKey: string;
} | null {
  if (!hasSupabaseConfig(env)) return null;

  return {
    url: env.NEXT_PUBLIC_SUPABASE_URL!,
    anonKey: env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  };
}
