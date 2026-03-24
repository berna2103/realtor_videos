import { createClient, SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

// Prevent multiple instances of Supabase client in development
const globalForSupabase = global as unknown as { supabase: SupabaseClient };

export const supabase =
  globalForSupabase.supabase || createClient(supabaseUrl, supabaseKey);

if (process.env.NODE_ENV !== 'production') globalForSupabase.supabase = supabase;