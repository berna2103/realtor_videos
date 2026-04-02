"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Video,
  Sparkles,
  LogOut,
  CheckCircle2,
  ArrowRight,
  Play,
  Film,
  Volume2,
  ShieldCheck,
  Share2,
  X
} from "lucide-react";

import { useAuth } from "../context/AuthContext";
import { supabase } from "../lib/supabase";

export default function LandingPage() {
  const { user, signOut } = useAuth();
  
  // Auth Modal States
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [isPlayingDemo, setIsPlayingDemo] = useState(false);

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    try {
      if (isSignUp) {
        const { error } = await supabase.auth.signUp({
          email: authEmail,
          password: authPassword,
        });
        if (error) throw error;
        alert("Check your email for a link!");
        setIsSignUp(false);
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email: authEmail,
          password: authPassword,
        });
        if (error) throw error;
        setShowAuthModal(false);
        // Redirect them to the dashboard upon successful login
        window.location.href = "/dashboard";
      }
    } catch (error: any) {
      alert(error.message);
    } finally {
      setAuthLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F9FAFB] text-slate-900 font-sans selection:bg-blue-100">
      
      {/* --- AUTH MODAL --- */}
      {showAuthModal && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-md">
          <div className="bg-white border border-slate-200 rounded-[2.5rem] w-full max-w-md p-10 shadow-2xl relative">
            <button
              onClick={() => setShowAuthModal(false)}
              className="absolute top-6 right-6 text-slate-400 hover:text-slate-600 transition-colors"
            >
              <X />
            </button>
            <div className="text-center mb-8">
              <div className="bg-blue-50 w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="text-blue-600 w-8 h-8" />
              </div>
              <h3 className="font-serif text-3xl font-bold text-slate-900 tracking-tight">
                Welcome Back
              </h3>
              <p className="text-slate-500 text-sm mt-2">
                Log in to render and manage your cinematic tours.
              </p>
            </div>
            <form onSubmit={handleAuthSubmit} className="space-y-4">
              <input
                type="email"
                required
                value={authEmail}
                onChange={(e) => setAuthEmail(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-4 text-slate-900 outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 transition-all"
                placeholder="Email address"
              />
              <input
                type="password"
                required
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-4 text-slate-900 outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 transition-all"
                placeholder="Password"
              />
              <button
                disabled={authLoading}
                className="w-full bg-slate-900 hover:bg-black transition-all py-4 rounded-xl font-bold text-white shadow-lg active:scale-[0.98]"
              >
                {authLoading ? "Authenticating..." : "Log In & Access Dashboard"}
              </button>
            </form>
            <button
              onClick={() => setIsSignUp(!isSignUp)}
              className="mt-6 text-xs text-blue-600 w-full text-center font-semibold hover:underline"
            >
              {isSignUp
                ? "Already have an account? Log In"
                : "Create a new agent account"}
            </button>
          </div>
        </div>
      )}

      {/* --- NAVIGATION --- */}
      {/* --- NAVIGATION --- */}
      <nav className="h-20 border-b border-slate-200 bg-white/80 backdrop-blur-xl fixed top-0 left-0 right-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-slate-900 p-2 rounded-xl shadow-lg shadow-slate-200">
              <Video className="w-5 h-5 text-white" />
            </div>
            <h1 className="font-serif text-2xl font-bold text-slate-900 tracking-tight">
              Cinematic<span className="text-blue-600 font-sans font-medium">AI</span>
            </h1>
          </div>
          
          <div className="flex items-center gap-2 sm:gap-4">
            {user ? (
              <div className="flex items-center gap-1 sm:gap-4 shrink-0">
                <Link
                  href="/dashboard"
                  className="hidden md:block text-sm font-bold text-slate-500 hover:text-slate-900 transition-colors"
                >
                  My Dashboard
                </Link>
                
                {/* Updated Sign Out Button with Icon */}
                <button
                  onClick={async () => {
                    await signOut();
                    window.location.reload(); 
                  }}
                  title="Sign Out"
                  className="p-2 rounded-full text-slate-400 hover:text-red-500 hover:bg-red-50 transition-all cursor-pointer flex items-center justify-center active:scale-95"
                >
                  <LogOut className="w-5 h-5" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowAuthModal(true)}
                className="hidden md:block text-sm font-bold text-slate-500 hover:text-slate-900 transition-colors cursor-pointer"
              >
                Sign In
              </button>
            )}
            
            <Link
              href="/create"
              className="text-sm font-bold bg-blue-600 text-white px-4 sm:px-6 py-2 sm:py-2.5 rounded-full shadow-lg hover:shadow-blue-200 hover:bg-blue-700 transition-all active:scale-95 whitespace-nowrap"
            >
              {user ? "Create Tour" : "Get Started Free"}
            </Link>
          </div>
        </div>
      </nav>

      {/* --- HERO SECTION --- */}
      <section className="pt-40 pb-20 px-6 relative overflow-hidden">
        {/* Background ambient glows */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-blue-500/10 blur-[100px] rounded-full pointer-events-none" />
        
        <div className="max-w-5xl mx-auto text-center relative z-10">
          <span className="inline-flex items-center gap-2 px-4 py-1.5 bg-blue-50 border border-blue-100 text-blue-700 rounded-full text-xs font-black uppercase tracking-widest mb-8">
            <Sparkles className="w-3.5 h-3.5" /> Stop Hiring Expensive Videographers
          </span>
          
          <h1 className="font-serif text-5xl md:text-7xl lg:text-8xl font-bold text-slate-900 mb-8 leading-[1.05] tracking-tight">
            Turn Zillow Links Into <br className="hidden md:block" />
            <span className="text-slate-400 italic font-medium relative">
              Studio-Quality
              {/* Gold underline accent mimicking your CSS --accent variable */}
              <svg className="absolute w-full h-3 -bottom-1 left-0 text-[#c5a059]/40" viewBox="0 0 100 10" preserveAspectRatio="none">
                <path d="M0 5 Q 50 10 100 5" stroke="currentColor" strokeWidth="4" fill="none" />
              </svg>
            </span> Tours.
          </h1>
          
          <p className="text-slate-500 text-lg md:text-xl mb-12 max-w-2xl mx-auto leading-relaxed">
            Generate breathtaking, cinematic property videos with lifelike AI voiceovers and dynamic camera movements in under 5 minutes. No editing skills required.
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/create"
              className="w-full sm:w-auto bg-slate-900 text-white px-8 py-4 rounded-2xl font-bold text-lg flex items-center justify-center gap-3 hover:bg-black transition-all shadow-xl hover:shadow-2xl active:scale-[0.98]"
            >
              Paste Your Listing Link <ArrowRight className="w-5 h-5 text-blue-400" />
            </Link>
            <button className="w-full sm:w-auto bg-white border border-slate-200 text-slate-700 px-8 py-4 rounded-2xl font-bold text-lg flex items-center justify-center gap-3 hover:bg-slate-50 transition-all shadow-sm">
              <Play className="w-5 h-5" /> Watch Demo
            </button>
          </div>
        </div>
      </section>

      {/* --- HOW IT WORKS (3 STEPS) --- */}
      <section className="py-24 bg-white border-y border-slate-100">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="font-serif text-4xl font-bold text-slate-900 tracking-tight">From Link to Lead-Magnet in Minutes</h2>
          </div>
          
          <div className="grid md:grid-cols-3 gap-8 relative">
            {/* Connecting Line */}
            <div className="hidden md:block absolute top-12 left-[15%] right-[15%] h-[2px] bg-slate-100 z-0" />
            
            {[
              {
                step: "01",
                title: "Paste URL",
                desc: "Simply drop in your Zillow or MLS link. Our AI instantly extracts high-res photos, descriptions, and property details."
              },
              {
                step: "02",
                title: "Customize Storyboard",
                desc: "Choose your cinematic camera pans, select a luxury AI narrator, and brand it with your brokerage logo."
              },
              {
                step: "03",
                title: "Render & Share",
                desc: "Download your stunning 4K 60FPS video in vertical or landscape format, perfectly optimized for Instagram Reels or YouTube."
              }
            ].map((item, i) => (
              <div key={i} className="relative z-10 bg-white border border-slate-200 p-8 rounded-[2rem] shadow-sm hover:shadow-xl hover:border-blue-200 transition-all duration-300">
                <div className="w-14 h-14 bg-slate-900 text-white rounded-2xl flex items-center justify-center font-serif text-xl font-bold mb-6 shadow-lg shadow-slate-900/20">
                  {item.step}
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-3">{item.title}</h3>
                <p className="text-slate-500 leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* --- FEATURES GRID --- */}
      <section className="py-24 px-6 bg-[#F9FAFB]">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div className="space-y-8">
              <h2 className="font-serif text-4xl md:text-5xl font-bold text-slate-900 tracking-tight">
                Everything you need to <span className="text-blue-600">win the listing.</span>
              </h2>
              <p className="text-slate-500 text-lg">
                Impress your sellers and dominate social media algorithms with high-retention video content that looks like it cost thousands of dollars to produce.
              </p>
              
              <div className="space-y-6">
                {[
                  { icon: Film, title: "Cinematic Camera Effects", desc: "Auto-applied 3D perspective pans, drone pulls, and slow zooms breathe life into static photos." },
                  { icon: Volume2, title: "Lifelike Neural Voices", desc: "English & Spanish professional voiceovers that sound warm, natural, and completely human." },
                  { icon: ShieldCheck, title: "Market Compliant", desc: "Automatically includes required MLS numbers, listing agent info, and brokerage logos to keep you out of trouble." },
                  { icon: Share2, title: "Social Media Ready", desc: "Export in Vertical (TikTok/Reels), Landscape (YouTube), or Square (Facebook) with one click." }
                ].map((Feature, i) => (
                  <div key={i} className="flex gap-4">
                    <div className="mt-1 bg-blue-50 p-3 rounded-xl h-fit">
                      <Feature.icon className="w-6 h-6 text-blue-600" />
                    </div>
                    <div>
                      <h4 className="font-bold text-slate-900 text-lg">{Feature.title}</h4>
                      <p className="text-slate-500 mt-1">{Feature.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
          
            {/* Visual Representation of the UI */}
            <div className="relative">
              <div className="absolute inset-0 bg-blue-600/5 blur-[100px] rounded-full" />
              <div className="relative bg-white p-4 rounded-[2.5rem] shadow-2xl border border-slate-200 transform rotate-2 hover:rotate-0 transition-all duration-500">
                
                {/* 👇 Updated Video Container */}
                <div 
                  className="aspect-[9/16] bg-slate-950 rounded-[2rem] overflow-hidden relative border-[8px] border-white shadow-inner cursor-pointer group"
                  onClick={() => setIsPlayingDemo(true)}
                >
                  {isPlayingDemo ? (
                    <video 
                      src={process.env.NEXT_PUBLIC_VIDEO_URL || "https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4"}
                      autoPlay 
                      controls 
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <>
                      {/* Mock Video UI */}
                      <img 
                        src="https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80" 
                        className="w-full h-full object-cover opacity-80 group-hover:scale-105 transition-transform duration-700" 
                        alt="Luxury home" 
                      />
                      <div className="absolute inset-0 bg-gradient-to-b from-black/20 via-transparent to-black/80" />
                      
                      {/* Play Button Mock */}
                      <div className="absolute inset-0 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                        <div className="w-16 h-16 bg-white/30 backdrop-blur-md rounded-full flex items-center justify-center border border-white/50 shadow-2xl">
                          <Play className="w-6 h-6 text-white ml-1" fill="currentColor" />
                        </div>
                      </div>

                      {/* Captions Mock */}
                      <div className="absolute bottom-10 left-6 right-6 text-center">
                        <p className="text-white font-sans font-bold text-lg drop-shadow-md bg-black/40 backdrop-blur-sm rounded-xl p-3 border border-white/10">
                          "Welcome to this stunning 4-bedroom luxury estate..."
                        </p>
                      </div>
                    </>
                  )}
                </div>

              </div>
            </div>
          </div>
        </div>
      </section>

      {/* --- PRICING CTA --- */}
      <section className="py-24 bg-white px-6">
        <div className="max-w-4xl mx-auto bg-slate-900 rounded-[3rem] p-10 md:p-16 text-center shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/20 blur-[80px] rounded-full" />
          
          <h2 className="font-serif text-4xl md:text-5xl font-bold text-white mb-6 relative z-10 tracking-tight">
            Ready to upgrade your marketing?
          </h2>
          <p className="text-slate-300 text-lg mb-10 max-w-xl mx-auto relative z-10">
            Join top producers who are saving thousands on video production while generating more buyer leads.
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-6 relative z-10">
            <Link
              href="/create"
              className="w-full sm:w-auto bg-blue-600 hover:bg-blue-500 text-white px-10 py-5 rounded-2xl font-bold text-lg transition-all shadow-xl active:scale-95"
            >
              Start Creating Now
            </Link>
            <div className="flex items-center gap-2 text-slate-300">
              <CheckCircle2 className="w-5 h-5 text-blue-400" />
              <span>5 HD Credits for just $25</span>
            </div>
          </div>
        </div>
      </section>

      {/* --- FOOTER --- */}
      <footer className="bg-[#F9FAFB] py-12 border-t border-slate-200">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6 text-sm text-slate-500">
          <div className="flex items-center gap-2">
            <Video className="w-4 h-4 text-slate-400" />
            <span className="font-bold text-slate-900">CinematicAI</span>
            <span>© {new Date().getFullYear()}</span>
          </div>
          <div className="flex gap-6">
            <Link href="#" className="hover:text-slate-900">Terms</Link>
            <Link href="#" className="hover:text-slate-900">Privacy</Link>
            <Link href="#" className="hover:text-slate-900">Contact</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}