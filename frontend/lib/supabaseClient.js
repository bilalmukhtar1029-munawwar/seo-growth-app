import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

// Falls back to a harmless placeholder client if env vars aren't set yet,
// so the app doesn't crash before you've created a Supabase project —
// auth calls will just fail gracefully with a clear error.
export const supabase = createClient(
  supabaseUrl || "https://placeholder.supabase.co",
  supabaseAnonKey || "placeholder-anon-key"
);

export const supabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);
