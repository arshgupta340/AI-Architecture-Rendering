import { NextResponse, type NextRequest } from "next/server";

import { createServerSupabase } from "@/lib/supabase/server";

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const next = url.searchParams.get("next") ?? "/";
  const destination = next.startsWith("/") ? next : "/";
  const supabase = await createServerSupabase();

  if (code && supabase) await supabase.auth.exchangeCodeForSession(code);
  return NextResponse.redirect(new URL(destination, url.origin));
}
