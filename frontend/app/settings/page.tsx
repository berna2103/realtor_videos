"use client";
import React, { useState, useEffect } from "react";
import Link from "next/link";
import { 
  User, Briefcase, Phone, Globe, Instagram, Upload, CreditCard, 
  Save, Loader2, Video, Coins, LayoutDashboard, LogOut 
} from "lucide-react";
import { useAuth } from "../../context/AuthContext"; 

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export default function SettingsPage() {
  const { user, email: userEmail, credits, signOut, isLoading: isAuthLoading } = useAuth();
  const [userId, setUserId] = useState<string | null>(null);
  
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  
  const [profile, setProfile] = useState({
    agent_name: "", brokerage: "", phone: "", website: "", social_handle: "",
    headshot_url: "", logo_url: "", headshot_data: "", logo_data: "",
  });

  // Fetch Auth User on Load
  useEffect(() => {
    if (!isAuthLoading) {
      if (user?.id) {
        setUserId(user.id);
        fetchProfile(user.id);
      } else {
        // Redirect to login if they try to access settings while logged out
        window.location.href = '/login'; 
      }
    }
  }, [user, isAuthLoading]);

  const fetchProfile = async (uid: string) => {
    try {
      const res = await fetch(`${API_URL}/api/profile/${uid}`);
      if (res.ok) {
        const data = await res.json();
        setProfile((prev) => ({ ...prev, ...data }));
      }
    } catch (error) {
      console.error("Failed to load profile", error);
    }
    setIsLoading(false);
  };

  const handleSave = async () => {
    if (!userId) return;
    setIsSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...profile, user_id: userId }),
      });
      if (res.ok) {
        const { profile: updatedProfile } = await res.json();
        setProfile((prev) => ({ ...prev, ...updatedProfile, headshot_data: "", logo_data: "" }));
        alert("Settings saved successfully!");
      }
    } catch (error) {
      console.error("Failed to save profile", error);
    }
    setIsSaving(false);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>, field: "headshot_data" | "logo_data") => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => setProfile({ ...profile, [field]: reader.result as string });
      reader.readAsDataURL(file);
    }
  };

  if (isLoading || isAuthLoading) return <div className="flex justify-center items-center h-screen bg-[#F9FAFB]"><Loader2 className="w-8 h-8 animate-spin text-blue-600" /></div>;

  return (
    <div className="min-h-screen bg-[#F9FAFB] text-slate-900 font-sans flex flex-col overflow-hidden">
      
      {/* --- TOP NAVIGATION --- */}
      <nav className="h-20 border-b border-slate-200 bg-white/80 backdrop-blur-xl flex items-center justify-between px-4 sm:px-8 z-30 relative shrink-0">
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <div className="bg-slate-900 p-1.5 sm:p-2 rounded-xl shadow-lg shadow-slate-200">
            <Video className="w-5 h-5 text-white" />
          </div>
          <h1 className="font-serif text-xl sm:text-2xl font-bold text-slate-900 tracking-tight hidden min-[380px]:block">
            Cinematic
            <span className="text-blue-600 font-sans font-medium">AI</span>
          </h1>
        </div>

        <div className="flex items-center gap-2 sm:gap-6">
          {user && (
            <div className="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-4 py-1.5 sm:py-2 bg-slate-50 border border-slate-200 rounded-full shrink-0">
              <Coins className="w-4 h-4 text-blue-600" />
              <span className="text-sm font-bold text-slate-700">
                {credits}
                <span className="hidden sm:inline"> Credits</span>
              </span>
            </div>
          )}

          {user && (
            <div className="flex items-center gap-1 sm:gap-4 shrink-0">
              <Link
                href="/create"
                className="p-1.5 sm:p-2 text-slate-400 hover:text-blue-600 transition-colors"
                title="Create New Tour"
              >
                <Video className="w-5 h-5" />
              </Link>
              <Link
                href="/dashboard"
                className="p-1.5 sm:p-2 text-slate-400 hover:text-blue-600 transition-colors"
                title="Dashboard"
              >
                <LayoutDashboard className="w-5 h-5" />
              </Link>

              <span className="text-sm text-slate-500 hidden md:block font-medium border-l border-slate-200 pl-4">
                {userEmail}
              </span>

              <button
                onClick={signOut}
                className="p-1.5 sm:p-2 text-slate-400 hover:text-red-500 transition-colors"
                title="Sign Out"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          )}
        </div>
      </nav>

      {/* --- MAIN SETTINGS CONTENT --- */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto p-4 sm:p-8 space-y-8 pb-20">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Account Settings</h1>
            <p className="text-slate-500 mt-1">Manage your branding, defaults, and subscription.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Left Column: Form */}
            <div className="md:col-span-2 space-y-6 bg-white p-6 sm:p-8 rounded-3xl border border-slate-200 shadow-sm">
              <h2 className="text-xl font-bold text-slate-800 border-b pb-4">Brand Profile</h2>
              
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase">Agent Name</label>
                  <div className="relative">
                    <User className="absolute left-3 top-3 w-5 h-5 text-slate-400" />
                    <input 
                      type="text" 
                      value={profile.agent_name} 
                      onChange={(e) => setProfile({...profile, agent_name: e.target.value})} 
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 p-3 text-slate-900 outline-none focus:border-blue-500 transition-colors" 
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase">Brokerage Name</label>
                  <div className="relative">
                    <Briefcase className="absolute left-3 top-3 w-5 h-5 text-slate-400" />
                    <input 
                      type="text" 
                      value={profile.brokerage} 
                      onChange={(e) => setProfile({...profile, brokerage: e.target.value})} 
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 p-3 text-slate-900 outline-none focus:border-blue-500 transition-colors" 
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase">Phone Number</label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-3 w-5 h-5 text-slate-400" />
                    <input 
                      type="text" 
                      value={profile.phone} 
                      onChange={(e) => setProfile({...profile, phone: e.target.value})} 
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 p-3 text-slate-900 outline-none focus:border-blue-500 transition-colors" 
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase">Instagram Handle</label>
                  <div className="relative">
                    <Instagram className="absolute left-3 top-3 w-5 h-5 text-slate-400" />
                    <input 
                      type="text" 
                      placeholder="@handle"
                      value={profile.social_handle} 
                      onChange={(e) => setProfile({...profile, social_handle: e.target.value})} 
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 p-3 text-slate-900 outline-none focus:border-blue-500 transition-colors" 
                    />
                  </div>
                </div>
                <div className="col-span-1 sm:col-span-2 space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase">Website</label>
                  <div className="relative">
                    <Globe className="absolute left-3 top-3 w-5 h-5 text-slate-400" />
                    <input 
                      type="text" 
                      value={profile.website} 
                      onChange={(e) => setProfile({...profile, website: e.target.value})} 
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 p-3 text-slate-900 outline-none focus:border-blue-500 transition-colors" 
                    />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-4 border-t border-slate-100">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase">Agent Headshot</label>
                  <label className="flex flex-col items-center justify-center border-2 border-dashed border-slate-200 bg-slate-50 p-6 rounded-2xl hover:border-blue-400 cursor-pointer overflow-hidden relative">
                    {(profile.headshot_data || profile.headshot_url) ? (
                      <img src={profile.headshot_data || profile.headshot_url} alt="Headshot" className="h-20 w-20 object-cover rounded-full shadow-md" />
                    ) : (
                      <>
                        <Upload className="w-6 h-6 text-slate-400 mb-2" />
                        <span className="text-xs font-bold text-slate-600">Upload Photo</span>
                      </>
                    )}
                    <input type="file" accept="image/*" onChange={(e) => handleFileUpload(e, "headshot_data")} className="hidden" />
                  </label>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase">Brokerage Logo</label>
                  <label className="flex flex-col items-center justify-center border-2 border-dashed border-slate-200 bg-slate-50 p-6 rounded-2xl hover:border-blue-400 cursor-pointer overflow-hidden relative">
                    {(profile.logo_data || profile.logo_url) ? (
                      <img src={profile.logo_data || profile.logo_url} alt="Logo" className="max-h-16 w-auto object-contain" />
                    ) : (
                      <>
                        <Upload className="w-6 h-6 text-slate-400 mb-2" />
                        <span className="text-xs font-bold text-slate-600">Upload Logo</span>
                      </>
                    )}
                    <input type="file" accept="image/*" onChange={(e) => handleFileUpload(e, "logo_data")} className="hidden" />
                  </label>
                </div>
              </div>

              <div className="pt-4">
                <button 
                  onClick={handleSave} 
                  disabled={isSaving}
                  className="w-full bg-slate-900 text-white font-bold py-4 rounded-xl flex items-center justify-center gap-2 hover:bg-slate-800 transition-colors disabled:opacity-50 active:scale-[0.98]"
                >
                  {isSaving ? <Loader2 className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
                  {isSaving ? "Saving Settings..." : "Save Profile Settings"}
                </button>
              </div>
            </div>

            {/* Right Column: Billing / Subscription Shell */}
            <div className="space-y-6">
              <div className="bg-gradient-to-br from-slate-900 to-slate-800 p-6 rounded-3xl text-white shadow-lg">
                <h2 className="text-lg font-bold flex items-center gap-2 mb-4">
                  <CreditCard className="w-5 h-5 text-blue-400" />
                  Subscription
                </h2>
                <div className="mb-6">
                  <p className="text-slate-400 text-sm">Current Plan</p>
                  <p className="text-2xl font-bold">Pro Agent</p>
                  <p className="text-sm text-slate-300 mt-1">{credits} Video Credits Remaining</p>
                </div>
                
                <button className="w-full bg-white/10 hover:bg-white/20 border border-white/20 text-white py-3 rounded-xl font-semibold transition-colors text-sm">
                  Manage Billing
                </button>
                <p className="text-[10px] text-slate-400 mt-3 text-center">Secure payments processed via Stripe.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}