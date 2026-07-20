import { describe, expect, it } from "vitest";

import { hasSupabaseConfig } from "./config";

describe("hasSupabaseConfig", () => {
  it("requires both the public URL and anonymous key", () => {
    expect(hasSupabaseConfig({})).toBe(false);
    expect(hasSupabaseConfig({ NEXT_PUBLIC_SUPABASE_URL: "https://example.supabase.co" })).toBe(false);
    expect(hasSupabaseConfig({ NEXT_PUBLIC_SUPABASE_ANON_KEY: "anon-key" })).toBe(false);
    expect(hasSupabaseConfig({
      NEXT_PUBLIC_SUPABASE_URL: "https://example.supabase.co",
      NEXT_PUBLIC_SUPABASE_ANON_KEY: "anon-key",
    })).toBe(true);
  });
});
