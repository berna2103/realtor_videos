import { createClient, SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

// Prevent multiple instances of Supabase client in development
const globalForSupabase = global as unknown as { supabase: SupabaseClient };

export const supabase =
  globalForSupabase.supabase || 
  createClient(supabaseUrl, supabaseKey, {
    auth: {
      storageKey: 'sb-auth-token', // Ensure consistent key
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      // If the lock error persists, you can try setting flowType or custom storage
    }
  });

if (process.env.NODE_ENV !== 'production') globalForSupabase.supabase = supabase;