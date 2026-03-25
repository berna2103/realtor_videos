"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Settings,
  Image as ImageIcon,
  Video,
  Upload,
  Trash2,
  ArrowUp,
  ArrowDown,
  Link as LinkIcon,
  Download,
  Share2,
  Loader2,
  CheckCircle2,
  ChevronRight,
  Palette,
  Clock,
  Sparkles,
  Film,
  Coins,
  CreditCard,
  LogIn,
  LogOut,
  X,
  User,
  Info,
  RefreshCw,
  AlertCircle,
  Plus,
} from "lucide-react";

import { useAuth } from "../context/AuthContext";
import { supabase } from "../../frontend/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const STRIPE_PRICE_ID_5_CREDITS =
  process.env.NEXT_PUBLIC_STRIPE_PRICE_ID || "price_XXXXXX";

interface Scene {
  id: string;
  image_path: string;
  image_url?: string;
  room_type: string;
  caption: string;
  effect: string;
  enable_vo: boolean;
}

interface Meta {
  address: string;
  price: string;
  beds: string;
  baths: string;
  sqft: string;
  agent: string;
  brokerage: string;
  mls_source: string;
  mls_number: string;
  phone: string;
  website: string;
}

const RENDER_MESSAGES = [
  "Spinning up the render engine...",
  "Downloading high-resolution photos...",
  "Generating AI voiceovers...",
  "Applying cinematic camera movements...",
  "Adding text overlays and branding...",
  "Stitching video frames... (This takes the longest)",
  "Mixing the audio tracks...",
  "Encoding final HD video...",
  "Almost there! Please don't close this tab...",
];

export default function CinematicListingApp() {
  const { user, email: userEmail, credits, signOut, refreshCredits } = useAuth();

  // Auth Modal States
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const [isOwnListing, setIsOwnListing] = useState<boolean>(true);
  const [showMobileSettings, setShowMobileSettings] = useState(false);
  const [showTopUpModal, setShowTopUpModal] = useState(false);

  // Workflow States
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [isLoading, setIsLoading] = useState(false);
  const [zillowUrl, setZillowUrl] = useState("");
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(false);
  const [renderMsgIdx, setRenderMsgIdx] = useState(0);

  // Media Settings
  const [format, setFormat] = useState("Vertical (1080x1920)");
  const [language, setLanguage] = useState("English");
  const [voice, setVoice] = useState("en-US-ChristopherNeural");
  const [font, setFont] = useState("Roboto");
  const [music, setMusic] = useState("real_estate_upbeat");
  const [timingMode, setTimingMode] = useState("Auto");
  const [primaryColor, setPrimaryColor] = useState("#552448");
  const [logoData, setLogoData] = useState<string | null>(null);

  const [meta, setMeta] = useState<Meta>({
    address: "",
    price: "",
    beds: "",
    baths: "",
    sqft: "",
    agent: "",
    brokerage: "",
    phone: "",
    website: "",
    mls_source: "",
    mls_number: "",
  });
  const [fbDraft, setFbDraft] = useState("");
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [statusChoice, setStatusChoice] = useState("Just Listed");
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);

  const isCompliant =
    isOwnListing ||
    (meta.agent && meta.brokerage && meta.mls_source && meta.mls_number);

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    try {
      if (isSignUp) {
        const { data, error } = await supabase.auth.signUp({
          email: authEmail,
          password: authPassword,
        });
        if (error) throw error;
        if (data.user && !data.session) {
          alert("Success! Check your inbox for a confirmation link.");
          setIsSignUp(false);
          setAuthPassword("");
        } else {
          setShowAuthModal(false);
        }
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email: authEmail,
          password: authPassword,
        });
        if (error) throw error;
        setShowAuthModal(false);
      }
    } catch (error: any) {
      alert(error.message || "Auth failed.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleBuyCredits = async () => {
    if (!user) return setShowAuthModal(true);
    setIsCheckingOut(true);
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId: user.id, priceId: STRIPE_PRICE_ID_5_CREDITS }),
      });
      const data = await res.json();
      if (data.url) window.location.href = data.url;
    } catch (e) {
      alert("Checkout failed.");
    } finally {
      setIsCheckingOut(false);
    }
  };

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => setLogoData(reader.result as string);
      reader.readAsDataURL(file);
    }
  };

  const handleFetchData = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/fetch-zillow`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ zillowUrl, language }),
      });
      if (response.status === 402) {
        setShowTopUpModal(true);
        return;
      }
      if (!response.ok) throw new Error("Backend error");
      const data = await response.json();
      setMeta({ ...meta, ...data.meta });
      setFbDraft(data.fbDraft);
      setScenes(data.scenes);
      setStep(2);
    } catch (error) {
      alert("Failed to fetch data.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleFacebookShare = async () => {
    if (!videoUrl) return;
    if (fbDraft) {
      try {
        await navigator.clipboard.writeText(fbDraft);
        alert("✅ Caption copied!");
      } catch (err) {
        console.error("Clipboard failed", err);
      }
    }
    const fbUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(videoUrl)}`;
    window.open(fbUrl, "_blank", "width=600,height=500,scrollbars=yes");
  };

  const handleRenderVideo = async () => {
    if (!user) return setShowAuthModal(true);
    if (credits !== null && credits < 1) return alert("Out of credits!");
    setIsRendering(true);
    setRenderMsgIdx(0);
    const msgInterval = setInterval(
      () => setRenderMsgIdx((p) => (p + 1) % RENDER_MESSAGES.length),
      8000
    );
    try {
      const res = await fetch(`${API_URL}/api/render-video`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: user.id,
          meta,
          scenes,
          format,
          language,
          voice,
          font,
          music,
          timing_mode: timingMode,
          show_price: true,
          show_details: true,
          status_choice: statusChoice,
          primary_color: primaryColor,
          logo_data: logoData,
        }),
      });
      const data = await res.json();
      const poll = setInterval(async () => {
        const sRes = await fetch(`${API_URL}/api/job-status/${data.job_id}`);
        const sData = await sRes.json();
        if (sData.status === "completed") {
          clearInterval(poll);
          clearInterval(msgInterval);
          setVideoUrl(sData.video_url);
          setIsRendering(false);
          setStep(3);
          refreshCredits();
        } else if (sData.status === "failed") {
          clearInterval(poll);
          clearInterval(msgInterval);
          alert(`Render failed. Check console for details.`);
          setIsRendering(false);
          refreshCredits();
        }
      }, 3000);
    } catch (e: any) {
      setIsRendering(false);
      clearInterval(msgInterval);
      alert(`Request failed: ${e.message || "Check console for details"}`);
      refreshCredits();
    }
  };

  const handleForceDownload = async () => {
    if (!videoUrl) return;
    setIsDownloading(true);
    try {
      const response = await fetch(videoUrl);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${meta.address || "video"}.mp4`;
      a.click();
    } catch (e) {
      window.open(videoUrl, "_blank");
    } finally {
      setIsDownloading(false);
    }
  };

  const updateScene = (index: number, field: keyof Scene, value: any) => {
    const newScenes = [...scenes];
    newScenes[index] = { ...newScenes[index], [field]: value };
    setScenes(newScenes);
  };

  const moveScene = (index: number, direction: "up" | "down") => {
    const newScenes = [...scenes];
    if (direction === "up" && index > 0)
      [newScenes[index - 1], newScenes[index]] = [
        newScenes[index],
        newScenes[index - 1],
      ];
    else if (direction === "down" && index < scenes.length - 1)
      [newScenes[index + 1], newScenes[index]] = [
        newScenes[index],
        newScenes[index + 1],
      ];
    setScenes(newScenes);
  };

  const removeScene = async (index: number) => {
    const scene = scenes[index];
    setScenes(scenes.filter((_, i) => i !== index));
    if (scene.image_url?.includes("supabase")) {
      const fileName = scene.image_url.split("/").pop()?.split("?")[0];
      if (fileName) await supabase.storage.from("listings").remove([fileName]);
    }
  };

  const handleStartOver = () => {
    setStep(1);
    setScenes([]);
    setZillowUrl("");
    setShowMobileSettings(false);
  };

  const SidebarSettings = () => (
    <div className="space-y-8">
      <section className="space-y-4">
        <h3 className="text-[10px] font-black text-neutral-500 uppercase tracking-widest flex items-center gap-2">
          <Palette className="w-3.5 h-3.5" /> Brand Identity
        </h3>
        <div className="space-y-3">
          <div className="flex items-center justify-between bg-neutral-900/50 p-2 rounded-lg border border-neutral-800">
            <span className="text-xs text-neutral-400">Primary Color</span>
            <input
              type="color"
              value={primaryColor}
              onChange={(e) => setPrimaryColor(e.target.value)}
              className="w-6 h-6 rounded bg-transparent border-none cursor-pointer"
            />
          </div>
          <div className="space-y-2">
            <span className="text-xs text-neutral-400">Brokerage Logo</span>
            {logoData ? (
              <div className="relative group rounded-lg overflow-hidden bg-neutral-950 border border-neutral-800 p-2">
                <img src={logoData} className="max-h-12 mx-auto object-contain" />
                <button
                  onClick={() => setLogoData(null)}
                  className="absolute inset-0 bg-red-500/80 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity"
                >
                  <Trash2 className="w-4 h-4 text-white" />
                </button>
              </div>
            ) : (
              <label className="flex flex-col items-center justify-center border border-dashed border-neutral-800 py-4 rounded-lg hover:bg-white/5 cursor-pointer transition-colors group">
                <Upload className="w-4 h-4 text-neutral-600 mb-1 group-hover:text-indigo-400" />
                <span className="text-[10px] text-neutral-500">Upload PNG</span>
                <input type="file" accept="image/*" onChange={handleLogoUpload} className="hidden" />
              </label>
            )}
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <h3 className="text-[10px] font-black text-neutral-500 uppercase tracking-widest flex items-center gap-2">
          <Settings className="w-3.5 h-3.5" /> Media Settings
        </h3>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-[11px] text-neutral-500 ml-1">Aspect Ratio</label>
            <select
              value={format}
              onChange={(e) => setFormat(e.target.value)}
              className="w-full bg-neutral-900 border border-neutral-800 rounded-lg p-2 text-xs focus:ring-1 focus:ring-indigo-500 outline-none"
            >
              <option>Vertical (1080x1920)</option>
              <option>Landscape (1920x1080)</option>
              <option>Square (1080x1080)</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-[11px] text-neutral-500 ml-1">Typography Style</label>
            <select
              value={font}
              onChange={(e) => setFont(e.target.value)}
              className="w-full bg-neutral-900 border border-neutral-800 rounded-lg p-2 text-xs outline-none"
            >
              <option value="Roboto">Roboto</option>
              <option value="Inter">Inter</option>
              <option value="Cinzel">Cinzel</option>
              <option value="Playfair">Playfair Display</option>
              <option value="Prata">Prata</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-[11px] text-neutral-500 ml-1">Voice & Language</label>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="bg-neutral-900 border border-neutral-800 rounded-lg p-2 text-xs outline-none"
              >
                <option>English</option>
                <option>Spanish</option>
              </select>
              <select
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
                className="bg-neutral-900 border border-neutral-800 rounded-lg p-2 text-xs outline-none"
              >
                <option value="en-US-ChristopherNeural">Christopher</option>
                <option value="en-US-JennyNeural">Jenny</option>
                <option value="es-MX-JorgeNeural">Jorge</option>
              </select>
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-[11px] text-neutral-500 ml-1">Soundtrack</label>
            <select
              value={music}
              onChange={(e) => setMusic(e.target.value)}
              className="w-full bg-neutral-900 border border-neutral-800 rounded-lg p-2 text-xs outline-none"
            >
              <option value="none">No Music</option>
              <option value="Upbeat">Upbeat</option>
              <option value="Luxury">Luxury</option>
              <option value="Motivation">Motivation</option>
            </select>
          </div>
        </div>
      </section>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-neutral-200 font-sans flex flex-col selection:bg-indigo-500/30 overflow-hidden">
      {/* AUTH MODAL */}
      {showAuthModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-md p-6 shadow-2xl">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-bold text-white">
                {isSignUp ? "Create Account" : "Welcome Back"}
              </h3>
              <button onClick={() => setShowAuthModal(false)}>
                <X className="w-5 h-5 text-neutral-500 hover:text-white" />
              </button>
            </div>
            <form onSubmit={handleAuthSubmit} className="space-y-4">
              <input
                type="email"
                required
                value={authEmail}
                onChange={(e) => setAuthEmail(e.target.value)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-3 text-sm focus:border-indigo-500 outline-none transition-all text-white"
                placeholder="Email"
              />
              <input
                type="password"
                required
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-3 text-sm focus:border-indigo-500 outline-none transition-all text-white"
                placeholder="Password"
              />
              <button
                disabled={authLoading}
                className="w-full bg-indigo-600 hover:bg-indigo-500 py-3 rounded-xl font-semibold text-white transition-colors flex items-center justify-center"
              >
                {authLoading ? <Loader2 className="animate-spin" /> : isSignUp ? "Sign Up" : "Log In"}
              </button>
            </form>
            <button
              onClick={() => setIsSignUp(!isSignUp)}
              className="mt-4 text-xs text-indigo-400 w-full text-center hover:underline"
            >
              {isSignUp ? "Already have an account? Log In" : "Don't have an account? Sign Up"}
            </button>
          </div>
        </div>
      )}

      {/* HEADER NAV */}
      <nav className="h-16 border-b border-neutral-800/60 bg-black/40 backdrop-blur-xl flex items-center justify-between px-6 z-30 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-br from-violet-600 to-indigo-600 p-1.5 rounded-lg">
            <Video className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-xl font-bold text-white hidden sm:block">
            Cinematic<span className="text-indigo-400 font-light">AI</span>
          </h1>
        </div>
        <div className="flex items-center gap-4">
          {user && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-neutral-900 border border-neutral-800 rounded-full">
              <Coins className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-bold text-neutral-300">{credits}</span>
              <button
                onClick={handleBuyCredits}
                className="ml-1 text-[10px] bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded-full hover:bg-indigo-500/30 transition-colors"
              >
                Top Up
              </button>
            </div>
          )}
          {user ? (
            <div className="flex items-center gap-3">
              <span className="text-xs text-neutral-500 hidden md:block">{userEmail}</span>
              <button
                onClick={signOut}
                className="p-2 text-neutral-500 hover:text-red-400 transition-colors"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowAuthModal(true)}
              className="text-sm font-semibold text-indigo-400 px-4 py-2 hover:bg-indigo-500/10 rounded-lg transition-colors"
            >
              Sign In
            </button>
          )}
        </div>
      </nav>

      <div className="flex flex-1 overflow-hidden relative">
        {/* DESKTOP SIDEBAR */}
        <aside className="hidden lg:flex w-72 border-r border-neutral-800/60 flex-col bg-neutral-950/20 overflow-y-auto p-6 gap-8 flex-shrink-0">
          <SidebarSettings />
          <div className="mt-auto space-y-2">
            {step > 1 && !isRendering && (
              <button
                onClick={handleStartOver}
                className="w-full p-3 bg-neutral-900 border border-neutral-800 rounded-xl text-xs text-neutral-400 hover:text-white transition-colors flex items-center justify-center gap-2"
              >
                <RefreshCw className="w-3 h-3" /> Start Over
              </button>
            )}
            {user && (
              <Link
                href="/dashboard"
                className="flex items-center justify-between p-3 bg-neutral-900/50 hover:bg-neutral-900 border border-neutral-800 rounded-xl transition-colors group"
              >
                <span className="text-xs font-medium flex items-center gap-2">
                  <Film className="w-4 h-4 text-indigo-400" /> Library
                </span>
                <ChevronRight className="w-4 h-4 text-neutral-600 group-hover:translate-x-1 transition-transform" />
              </Link>
            )}
          </div>
        </aside>

        {/* MAIN CANVAS */}
        <main className="flex-1 overflow-y-auto custom-scrollbar bg-[radial-gradient(circle_at_top,_var(--tw-gradient-stops))] from-indigo-500/5 via-transparent to-transparent">
          <div className="max-w-4xl mx-auto p-6 md:p-12">
            {isRendering ? (
              <div className="flex flex-col items-center justify-center min-h-[60vh] py-12 animate-in fade-in duration-700">
                <div className="w-32 h-32 rounded-full border-2 border-indigo-500/30 flex items-center justify-center bg-neutral-900 mb-12">
                  <Loader2 className="w-12 h-12 text-indigo-500 animate-spin" />
                </div>
                <h2 className="text-4xl font-black text-white mb-4 tracking-tighter">Crafting Your Tour</h2>
                <p className="text-xl text-indigo-300 font-medium animate-pulse text-center max-w-md">
                  {RENDER_MESSAGES[renderMsgIdx]}
                </p>
                <div className="mt-12 bg-neutral-900/80 border border-neutral-800 p-6 rounded-2xl flex items-start gap-4 max-w-sm">
                  <Clock className="w-5 h-5 text-amber-500 shrink-0 mt-1" />
                  <p className="text-sm text-neutral-400">
                    Rendering takes <strong className="text-white">up to 5 minutes</strong>. Keep this tab open.
                  </p>
                </div>
              </div>
            ) : step === 1 ? (
              <div className="text-center py-20 animate-in fade-in slide-in-from-bottom-6 duration-700">
                <h2 className="text-5xl md:text-7xl font-black text-white tracking-tighter mb-6 leading-[0.9]">
                  Turn any listing <br /> into cinema.
                </h2>
                <div className="p-2 bg-neutral-900/40 border border-neutral-800 rounded-2xl max-w-2xl mx-auto flex flex-col sm:flex-row gap-2 shadow-2xl backdrop-blur-xl">
                  <div className="relative flex-1 flex items-center px-4">
                    <LinkIcon className="w-5 h-5 text-neutral-600 mr-3" />
                    <input
                      type="text"
                      value={zillowUrl}
                      onChange={(e) => setZillowUrl(e.target.value)}
                      placeholder="https://www.zillow.com/homedetails/..."
                      className="w-full bg-transparent py-4 text-white focus:outline-none placeholder:text-neutral-700 font-medium"
                    />
                  </div>
                  <button
                    onClick={handleFetchData}
                    disabled={isLoading || !zillowUrl}
                    className="bg-white hover:bg-neutral-200 text-black px-8 py-4 rounded-xl font-bold transition-all min-w-[160px]"
                  >
                    {isLoading ? <Loader2 className="animate-spin mx-auto" /> : "Build Tour"}
                  </button>
                </div>
              </div>
            ) : step === 2 ? (
              <div className="space-y-12 pb-32 animate-in fade-in duration-700">
                <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                  <div>
                    <h2 className="text-4xl font-black text-white tracking-tighter">Production Suite</h2>
                    <p className="text-neutral-500 font-medium">Fine-tune your scenes.</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {[
                      "Coming Soon",
                      "Just Listed",
                      "Home For Sale",
                      "Open House",
                      "Price Reduced",
                      "Under Contract",
                      "Just Sold",
                    ].map((s) => (
                      <button
                        key={s}
                        onClick={() => setStatusChoice(s)}
                        className={`px-4 py-2 rounded-full text-[10px] font-black uppercase tracking-widest transition-all border ${statusChoice === s ? "bg-indigo-600 text-white border-indigo-500 shadow-lg shadow-indigo-500/30" : "bg-neutral-900 text-neutral-500 border-neutral-800 hover:border-neutral-700"}`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </header>

                <div className="grid grid-cols-1 gap-10">
                  {scenes.map((scene, index) => (
                    <div
                      key={scene.id}
                      className="group flex flex-col lg:flex-row bg-neutral-900/40 border border-neutral-800 rounded-3xl overflow-hidden hover:border-indigo-500/30 transition-all duration-500"
                    >
                      <div className="lg:w-[40%] aspect-video bg-black relative overflow-hidden">
                        <img
                          src={scene.image_url}
                          className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-all duration-700"
                        />
                        <div className="absolute top-4 left-4 bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 text-[10px] font-black text-indigo-400 tracking-tighter">
                          SCENE {index + 1}
                        </div>
                      </div>
                      <div className="flex-1 p-8 flex flex-col justify-between gap-6">
                        <div className="space-y-2">
                          <label className="text-[10px] font-black text-neutral-500 uppercase tracking-widest">
                            Voiceover Script
                          </label>
                          <textarea
                            value={scene.caption}
                            onChange={(e) => updateScene(index, "caption", e.target.value)}
                            className="w-full bg-neutral-950/50 border border-neutral-800 rounded-xl p-4 text-sm font-medium focus:border-indigo-500/50 outline-none transition-all resize-none leading-relaxed h-28"
                          />
                        </div>
                        <div className="flex flex-col sm:flex-row items-center gap-4 pt-4 border-t border-neutral-800/50">
                          <select
                            value={scene.effect}
                            onChange={(e) => updateScene(index, "effect", e.target.value)}
                            className="flex-1 w-full bg-neutral-950 border border-neutral-800 rounded-xl p-3 text-xs font-bold outline-none focus:border-indigo-500/50"
                          >
                            <option value="zoom_in">Slow Zoom In</option>
                            <option value="drone_rise">Drone Rise</option>
                            <option value="parallax_depth">Parallax</option>
                          </select>
                          <div className="flex items-center gap-1.5 ml-auto">
                            <button
                              onClick={() => moveScene(index, "up")}
                              disabled={index === 0}
                              className="p-2 bg-neutral-950 border border-neutral-800 rounded-lg hover:text-white disabled:opacity-20 transition-colors"
                            >
                              <ArrowUp className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => moveScene(index, "down")}
                              disabled={index === scenes.length - 1}
                              className="p-2 bg-neutral-950 border border-neutral-800 rounded-lg hover:text-white disabled:opacity-20 transition-colors"
                            >
                              <ArrowDown className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => removeScene(index)}
                              className="p-2 bg-red-500/10 text-red-400 border border-red-500/20 rounded-lg hover:bg-red-500/20 transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="max-w-3xl mx-auto py-12 animate-in fade-in zoom-in-95 duration-700">
                <div className="text-center mb-12">
                  <div className="w-20 h-20 bg-emerald-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
                    <CheckCircle2 className="w-10 h-10 text-emerald-500" />
                  </div>
                  <h2 className="text-4xl font-black text-white tracking-tighter">Tour is Ready</h2>
                </div>
                <div
                  className={`mx-auto bg-black rounded-[32px] overflow-hidden shadow-2xl ring-1 ring-white/10 ${format.includes("Vertical") ? "aspect-[9/16] w-72" : "aspect-video w-full"}`}
                >
                  <video src={videoUrl!} controls autoPlay className="w-full h-full object-contain" />
                </div>
                <div className="flex flex-col sm:flex-row justify-center gap-4 mt-12">
                  <button
                    onClick={handleForceDownload}
                    disabled={isDownloading}
                    className="flex-1 bg-white text-black py-4 rounded-2xl font-bold flex items-center justify-center gap-2 hover:bg-neutral-200 transition-all"
                  >
                    {isDownloading ? <Loader2 className="animate-spin" /> : <Download className="w-5 h-5" />} Download MP4
                  </button>
                  <button
                    onClick={handleFacebookShare}
                    className="flex-1 bg-[#1877F2] text-white py-4 rounded-2xl font-bold flex items-center justify-center gap-2 hover:bg-[#166fe5] transition-all"
                  >
                    <Share2 className="w-5 h-5" /> Facebook
                  </button>
                </div>
              </div>
            )}
          </div>
        </main>

        {/* DESKTOP RIGHT SIDEBAR */}
        {step === 2 && !isRendering && (
          <aside className="hidden xl:flex w-80 border-l border-neutral-800/60 flex-col bg-neutral-950/20 overflow-y-auto p-6 gap-8 flex-shrink-0">
            <section className="space-y-6">
              <h3 className="text-[10px] font-black text-neutral-500 uppercase tracking-widest">Metadata</h3>
              <div className="space-y-4">
                {[
                  { label: "Address", key: "address" },
                  { label: "Price", key: "price" },
                  { label: "Beds", key: "beds", short: true },
                  { label: "Baths", key: "baths", short: true },
                  { label: "SqFt", key: "sqft", short: true },
                ].map((f) => (
                  <div key={f.key} className={f.short ? "inline-block w-1/3 pr-2" : ""}>
                    <label className="text-[10px] text-neutral-600 mb-1 block uppercase tracking-tighter">{f.label}</label>
                    <input
                      type="text"
                      value={(meta as any)[f.key]}
                      onChange={(e) => setMeta({ ...meta, [f.key]: e.target.value })}
                      className="w-full bg-neutral-900 border border-neutral-800 rounded-lg p-2 text-xs text-white outline-none focus:border-indigo-500/50"
                    />
                  </div>
                ))}
              </div>
            </section>

            <section className="space-y-4">
              <h3 className="text-[10px] font-black text-neutral-500 uppercase tracking-widest">Compliance</h3>
              <div className="bg-amber-500/5 border border-amber-500/10 p-4 rounded-xl space-y-4">
                <div className="flex gap-2 p-1 bg-black rounded-lg border border-neutral-800">
                  <button
                    onClick={() => setIsOwnListing(true)}
                    className={`flex-1 py-1.5 text-[10px] font-black uppercase rounded-md transition-all ${isOwnListing ? "bg-indigo-600 text-white shadow-sm" : "text-neutral-500"}`}
                  >
                    My Listing
                  </button>
                  <button
                    onClick={() => setIsOwnListing(false)}
                    className={`flex-1 py-1.5 text-[10px] font-black uppercase rounded-md transition-all ${!isOwnListing ? "bg-indigo-600 text-white shadow-sm" : "text-neutral-500"}`}
                  >
                    Co-Broke
                  </button>
                </div>
                {!isOwnListing && (
                  <div className="space-y-3 animate-in fade-in duration-300">
                    <input
                      type="text"
                      placeholder="Listing Agent"
                      value={meta.agent}
                      onChange={(e) => setMeta({ ...meta, agent: e.target.value })}
                      className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-2 text-xs outline-none focus:border-indigo-500/50"
                    />
                    <input
                      type="text"
                      placeholder="Brokerage"
                      value={meta.brokerage}
                      onChange={(e) => setMeta({ ...meta, brokerage: e.target.value })}
                      className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-2 text-xs outline-none focus:border-indigo-500/50"
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        type="text"
                        placeholder="Source"
                        value={meta.mls_source}
                        onChange={(e) => setMeta({ ...meta, mls_source: e.target.value })}
                        className="bg-neutral-950 border border-neutral-800 rounded-lg p-2 text-xs outline-none"
                      />
                      <input
                        type="text"
                        placeholder="MLS #"
                        value={meta.mls_number}
                        onChange={(e) => setMeta({ ...meta, mls_number: e.target.value })}
                        className="bg-neutral-950 border border-neutral-800 rounded-lg p-2 text-xs outline-none"
                      />
                    </div>
                  </div>
                )}
              </div>
            </section>

            <div className="mt-auto">
              <button
                onClick={handleRenderVideo}
                disabled={!isCompliant}
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white py-5 rounded-[24px] font-black uppercase tracking-widest text-xs shadow-2xl shadow-indigo-600/40 transition-all flex items-center justify-center gap-3 disabled:opacity-30"
              >
                <Film className="w-5 h-5" /> Render Tour
              </button>
              {!isCompliant && (
                <p className="text-[10px] text-red-400 mt-3 text-center animate-pulse tracking-tighter">
                  Missing attribution details
                </p>
              )}
            </div>
          </aside>
        )}
      </div>

      {/* MOBILE SETTINGS DRAWER */}
      {showMobileSettings && (
        <div className="fixed inset-0 z-50 lg:hidden animate-in fade-in duration-200">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setShowMobileSettings(false)}
          />
          <div className="absolute bottom-0 left-0 right-0 bg-neutral-900 border-t border-neutral-800 rounded-t-[32px] p-8 max-h-[85vh] overflow-y-auto slide-in-from-bottom duration-300">
            <div className="flex justify-between items-center mb-8">
              <h3 className="text-xl font-bold text-white tracking-tight">Production Settings</h3>
              <button onClick={() => setShowMobileSettings(false)} className="p-2 bg-neutral-800 rounded-full text-neutral-400">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-8">
              <SidebarSettings />
              <button
                onClick={handleStartOver}
                className="w-full p-4 bg-red-500/10 text-red-400 border border-red-500/20 rounded-xl text-xs font-black uppercase tracking-widest transition-all"
              >
                Start Over
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MOBILE ACTION BAR */}
      {step === 2 && !isRendering && (
        <div className="lg:hidden fixed bottom-0 left-0 right-0 p-4 bg-black/80 backdrop-blur-xl border-t border-neutral-800 z-40 flex gap-3">
          <button
            onClick={() => setShowMobileSettings(true)}
            className="p-4 bg-neutral-900 border border-neutral-800 rounded-2xl text-white shadow-xl transition-all active:scale-95 flex items-center justify-center"
          >
            <Settings className="w-6 h-6" />
          </button>
          <button
            onClick={handleRenderVideo}
            disabled={!isCompliant}
            className="flex-1 bg-indigo-600 py-4 rounded-2xl font-black uppercase tracking-widest text-xs text-white flex items-center justify-center gap-2 shadow-xl shadow-indigo-600/30 disabled:opacity-30 active:scale-95 transition-all"
          >
            <Film className="w-5 h-5" /> Render HD Tour
          </button>
        </div>
      )}

      {/* INSUFFICIENT CREDITS MODAL */}
      {showTopUpModal && (
        <div className="fixed inset-0 bg-black/90 backdrop-blur-md z-50 flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-neutral-900 border border-white/10 p-8 md:p-12 rounded-[2.5rem] max-w-md w-full text-center relative shadow-2xl">
            <div className="bg-amber-500/10 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 border border-amber-500/20">
              <AlertCircle className="w-10 h-10 text-amber-500" />
            </div>
            <h2 className="text-3xl font-bold text-white mb-4">Wallet Empty</h2>
            <p className="text-neutral-400 mb-8 leading-relaxed">
              To keep our AI engines running and rendering cinematic videos, we require active credits. Top up now to
              continue.
            </p>
            <div className="flex flex-col gap-3">
              <button
                onClick={handleBuyCredits}
                className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 rounded-2xl transition-all shadow-lg shadow-indigo-500/20 flex items-center justify-center gap-2"
              >
                <Plus className="w-5 h-5" /> Buy Credits
              </button>
              <button
                onClick={() => setShowTopUpModal(false)}
                className="py-3 text-neutral-500 hover:text-white transition-colors text-sm font-medium"
              >
                Return to Dashboard
              </button>
            </div>
            <p className="mt-8 text-[10px] text-neutral-600 uppercase tracking-widest font-bold">
              Secure Checkout via Stripe
            </p>
          </div>
        </div>
      )}
    </div>
  );
}