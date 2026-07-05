import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

/** Devuelve access_token de la sesión (cookies vía SSR). */
export async function GET() {
  const supabase = await createClient();
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser();

  if (userError || !user) {
    return NextResponse.json(
      { access_token: null, detail: userError?.message ?? "Not signed in" },
      { status: 401 },
    );
  }

  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    return NextResponse.json(
      { access_token: null, detail: "No session" },
      { status: 401 },
    );
  }

  return NextResponse.json({ access_token: session.access_token });
}
