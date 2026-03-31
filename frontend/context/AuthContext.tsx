"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { User } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";

interface AuthContextType {
  user: User | null;
  email: string | null;
  credits: number | null;
  isLoading: boolean;
  refreshCredits: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [credits, setCredits] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchCredits = useCallback(async (userId: string) => {
    try {
      const { data } = await supabase
        .from("user_credits")
        .select("balance")
        .eq("user_id", userId)
        .maybeSingle();
      setCredits(data ? data.balance : 0);
    } catch (error) {
      console.error("Error fetching credits:", error);
    }
  }, []);

  const refreshCredits = useCallback(async () => {
    if (user) await fetchCredits(user.id);
  }, [user, fetchCredits]);

  const signOut = async () => {
    await supabase.auth.signOut();
    setUser(null);
    setCredits(null);
  };

  useEffect(() => {
    let isMounted = true;

    const initSession = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.user && isMounted) {
        setUser(session.user);
        await fetchCredits(session.user.id);
      }
      if (isMounted) setIsLoading(false);
    };

    initSession();

    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (isMounted) {
        if (session?.user) {
          setUser(session.user);
          await fetchCredits(session.user.id);
        } else {
          setUser(null);
          setCredits(null);
        }
        setIsLoading(false);
      }
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, [fetchCredits]);

  return (
    <AuthContext.Provider value={{ user, email: user?.email || null, credits, isLoading, refreshCredits, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) throw new Error("useAuth must be used within an AuthProvider");
  return context;
};