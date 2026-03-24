"use client";

import { useState, useEffect } from "react";
import { createClient } from "@supabase/supabase-js";
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
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const STRIPE_PRICE_ID_5_CREDITS =
  process.env.NEXT_PUBLIC_STRIPE_PRICE_ID || "price_XXXXXX";

// Initialize Supabase client
import { supabase } from "../../frontend/lib/supabase"; // Adjust the path as needed

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
  // --- AUTHENTICATION STATES ---
  const [userId, setUserId] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [credits, setCredits] = useState<number | null>(null);

  // Auth Modal States
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const [isOwnListing, setIsOwnListing] = useState<boolean>(true);

  // --- ORIGINAL STATES ---
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [isLoading, setIsLoading] = useState(false);
  const [zillowUrl, setZillowUrl] = useState("");
  const [videoUrl, setVideoUrl] = useState<string | null>(null);

  const [isRendering, setIsRendering] = useState(false);
  const [renderMsgIdx, setRenderMsgIdx] = useState(0);

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

  // --- FETCH USER & CREDITS ON LOAD ---
  const fetchUserAndCredits = async () => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (session?.user) {
      setUserId(session.user.id);
      setUserEmail(session.user.email || null);

      const { data, error } = await supabase
        .from("user_credits")
        .select("balance")
        .eq("user_id", session.user.id)
        .maybeSingle(); // <-- CHANGED FROM .single()

      if (data) setCredits(data.balance);
      else setCredits(0); // Safely defaults to 0 if no row exists yet
    } else {
      setUserId(null);
      setUserEmail(null);
      setCredits(null);
    }
  };

  useEffect(() => {
    fetchUserAndCredits();

    // Listen for auth changes (like logging in or out)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(() => {
      fetchUserAndCredits();
    });
    return () => subscription.unsubscribe();
  }, []);

  // --- AUTHENTICATION HANDLERS ---
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

        // Check if email confirmation is required (User exists, but no active session)
        if (data.user && !data.session) {
          alert(
            "Success! Please check your email inbox for a confirmation link to activate your account.",
          );
          setIsSignUp(false); // Flip the modal to "Log In" mode for when they come back
          setAuthPassword(""); // Clear the password for security
        } else {
          // If email confirmation is turned off in Supabase
          alert("Account created successfully! You are now logged in.");
          setShowAuthModal(false);
          setAuthEmail("");
          setAuthPassword("");
        }
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email: authEmail,
          password: authPassword,
        });
        if (error) throw error;
        setShowAuthModal(false);
        setAuthEmail("");
        setAuthPassword("");
      }
    } catch (error: any) {
      alert(error.message || "An error occurred during authentication.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSignOut = async () => {
    await supabase.auth.signOut();
  };

  // --- STRIPE CHECKOUT ---
  const handleBuyCredits = async () => {
    if (!userId) return setShowAuthModal(true); // Open modal instead of alert
    setIsCheckingOut(true);
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId, priceId: STRIPE_PRICE_ID_5_CREDITS }),
      });
      const data = await res.json();
      if (data.url) window.location.href = data.url;
    } catch (e) {
      console.error(e);
      alert("Checkout failed.");
    } finally {
      setIsCheckingOut(false);
    }
  };

  // --- ORIGINAL FUNCTIONS ---
  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => setLogoData(reader.result as string);
      reader.readAsDataURL(file);
    }
  };

  const removeLogo = () => setLogoData(null);

  const handleFetchData = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/fetch-zillow`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ zillowUrl, language }),
      });

      if (!response.ok) throw new Error("Backend returned an error");

      const data = await response.json();
      setMeta({ ...meta, ...data.meta });
      setFbDraft(data.fbDraft);
      setScenes(data.scenes);
      setStep(2);
    } catch (error) {
      console.error(error);
      alert(
        "Failed to fetch data. Make sure your backend is running and URL is correct!",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleRenderVideo = async () => {
    if (!userId) return setShowAuthModal(true); // Open modal if not logged in
    if (credits !== null && credits < 1) {
      alert("You are out of credits! Please top up your wallet to render.");
      return;
    }

    setIsRendering(true);
    setRenderMsgIdx(0);
    const msgInterval = setInterval(() => {
      setRenderMsgIdx((prev) => (prev + 1) % RENDER_MESSAGES.length);
    }, 8000);

    try {
      if (credits !== null) setCredits(credits - 1);

      const res = await fetch(`${API_URL}/api/render-video`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
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

      if (!res.ok) {
        if (res.status === 402)
          alert("Insufficient credits detected by server.");
        throw new Error("Render request failed");
      }

      const data = await res.json();
      const jobId = data.job_id;

      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`${API_URL}/api/job-status/${jobId}`);

          if (!statusRes.ok) {
            clearInterval(pollInterval);
            clearInterval(msgInterval);
            alert("Connection lost or server restarted. The render failed.");
            setIsRendering(false);
            if (credits !== null) setCredits(credits);
            return;
          }

          const statusData = await statusRes.json();

          if (statusData.status === "completed") {
            clearInterval(pollInterval);
            clearInterval(msgInterval);
            setVideoUrl(statusData.video_url);
            setIsRendering(false);
            setStep(3);
            fetchUserAndCredits(); // Refresh credits securely from server
          } else if (statusData.status === "failed") {
            clearInterval(pollInterval);
            clearInterval(msgInterval);
            alert("Render failed: " + statusData.error);
            setIsRendering(false);
            if (credits !== null) setCredits(credits);
          }
        } catch (e) {
          console.error("Polling error", e);
        }
      }, 3000);
    } catch (error) {
      console.error(error);
      clearInterval(msgInterval);
      alert("Failed to connect to the render engine.");
      setIsRendering(false);
      if (credits !== null) setCredits(credits);
    }
  };

  const handleForceDownload = async () => {
    if (!videoUrl) return;
    setIsDownloading(true);
    setDownloadProgress(0);
    try {
      const response = await fetch(videoUrl);
      if (!response.ok) throw new Error("Network response was not ok");
      const contentLength = response.headers.get("content-length");
      const total = contentLength ? parseInt(contentLength, 10) : 0;
      let blob;
      if (total && response.body) {
        const reader = response.body.getReader();
        let received = 0;
        const chunks = [];
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          chunks.push(value);
          received += value.length;
          setDownloadProgress(Math.round((received / total) * 100));
        }
        blob = new Blob(chunks, {
          type: response.headers.get("content-type") || "video/mp4",
        });
      } else {
        blob = await response.blob();
        setDownloadProgress(100);
      }
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = blobUrl;
      const safeName = meta.address
        ? meta.address.replace(/[^a-z0-9]/gi, "_").toLowerCase()
        : "cinematic-listing";
      a.download = `${safeName}.mp4`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(blobUrl);
      document.body.removeChild(a);
    } catch (error) {
      window.open(videoUrl, "_blank");
    } finally {
      setTimeout(() => {
        setIsDownloading(false);
        setDownloadProgress(0);
      }, 1000);
    }
  };

  const updateScene = (index: number, field: keyof Scene, value: any) => {
    const newScenes = [...scenes];
    newScenes[index] = { ...newScenes[index], [field]: value };
    setScenes(newScenes);
  };
  const moveScene = (index: number, direction: "up" | "down") => {
    const newScenes = [...scenes];
    if (direction === "up" && index > 0) {
      [newScenes[index - 1], newScenes[index]] = [
        newScenes[index],
        newScenes[index - 1],
      ];
      setScenes(newScenes);
    } else if (direction === "down" && index < scenes.length - 1) {
      [newScenes[index + 1], newScenes[index]] = [
        newScenes[index],
        newScenes[index + 1],
      ];
      setScenes(newScenes);
    }
  };
  const removeScene = (index: number) =>
    setScenes(scenes.filter((_, i) => i !== index));

  const StepIndicator = () => (
    <div className="flex items-center justify-center gap-2 mb-8 text-sm font-medium">
      <div
        className={`flex items-center gap-2 ${step >= 1 ? "text-indigo-400" : "text-neutral-600"}`}
      >
        <span
          className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${step >= 1 ? "bg-indigo-500/20" : "bg-neutral-800"}`}
        >
          1
        </span>{" "}
        Extract
      </div>
      <ChevronRight className="w-4 h-4 text-neutral-600" />
      <div
        className={`flex items-center gap-2 ${step >= 2 ? "text-indigo-400" : "text-neutral-600"}`}
      >
        <span
          className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${step >= 2 ? "bg-indigo-500/20" : "bg-neutral-800"}`}
        >
          2
        </span>{" "}
        Storyboard
      </div>
      <ChevronRight className="w-4 h-4 text-neutral-600" />
      <div
        className={`flex items-center gap-2 ${step === 3 ? "text-indigo-400" : "text-neutral-600"}`}
      >
        <span
          className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${step === 3 ? "bg-indigo-500/20" : "bg-neutral-800"}`}
        >
          3
        </span>{" "}
        Render
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-neutral-200 font-sans flex flex-col md:flex-row selection:bg-indigo-500/30">
      {/* AUTH MODAL OVERLAY */}
      {showAuthModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-md p-6 shadow-2xl shadow-indigo-500/10">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-bold text-white">
                {isSignUp ? "Create an Account" : "Welcome Back"}
              </h3>
              <button
                onClick={() => setShowAuthModal(false)}
                className="text-neutral-500 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAuthSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-neutral-400 mb-1.5">
                  Email
                </label>
                <input
                  type="email"
                  required
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-3 text-sm focus:border-indigo-500 outline-none transition-all text-white"
                  placeholder="agent@example.com"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-neutral-400 mb-1.5">
                  Password
                </label>
                <input
                  type="password"
                  required
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-3 text-sm focus:border-indigo-500 outline-none transition-all text-white"
                  placeholder="••••••••"
                />
              </div>
              <button
                disabled={authLoading}
                type="submit"
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 rounded-xl transition-all flex items-center justify-center mt-2 disabled:opacity-50"
              >
                {authLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : isSignUp ? (
                  "Sign Up"
                ) : (
                  "Log In"
                )}
              </button>
            </form>

            <div className="mt-6 text-center text-sm text-neutral-500">
              {isSignUp ? "Already have an account?" : "Don't have an account?"}
              <button
                onClick={() => setIsSignUp(!isSignUp)}
                className="ml-2 text-indigo-400 hover:text-indigo-300 font-medium"
              >
                {isSignUp ? "Log In" : "Sign Up"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* SIDEBAR */}
      <aside className="w-full md:w-80 bg-neutral-900/40 backdrop-blur-xl border-r border-neutral-800/60 p-6 flex flex-col gap-6 overflow-y-auto order-2 md:order-1 z-10">
        <div className="flex flex-col gap-4 pb-4 border-b border-neutral-800/60">
          <div className="flex items-center gap-3">
            <div className="bg-gradient-to-br from-violet-600 to-indigo-600 p-2 rounded-lg shadow-lg shadow-indigo-500/20">
              <Video className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-xl font-bold tracking-tight text-white">
              Cinematic<span className="text-indigo-400 font-light">AI</span>
            </h1>
          </div>

          {/* USER PROFILE & WALLET UI */}
          <div className="flex flex-col gap-3">
            {userId ? (
              <div className="bg-neutral-950/50 border border-neutral-800 rounded-xl p-3 flex items-center justify-between">
                <div className="flex items-center gap-2.5 overflow-hidden">
                  <div className="bg-neutral-800 p-1.5 rounded-full">
                    <User className="w-4 h-4 text-neutral-400" />
                  </div>
                  <span className="text-xs font-medium text-neutral-300 truncate">
                    {userEmail}
                  </span>
                </div>
                <button
                  onClick={handleSignOut}
                  className="text-xs text-neutral-500 hover:text-red-400 transition-colors p-1.5"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowAuthModal(true)}
                className="w-full bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 rounded-xl p-3 text-sm font-medium text-neutral-300 transition-colors flex items-center justify-center gap-2"
              >
                <LogIn className="w-4 h-4" /> Sign In or Create Account
              </button>
            )}

            <div className="bg-neutral-950 border border-neutral-800 rounded-xl p-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Coins className="w-4 h-4 text-amber-400" />
                <span className="text-sm font-medium text-neutral-300">
                  {credits !== null ? `${credits} Credits` : "0 Credits"}
                </span>
              </div>
              <button
                onClick={handleBuyCredits}
                disabled={isCheckingOut}
                className="text-xs bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 font-semibold px-3 py-1.5 rounded-md transition-colors flex items-center gap-1.5"
              >
                {isCheckingOut ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <CreditCard className="w-3 h-3" />
                )}{" "}
                Top Up
              </button>
            </div>
          </div>
        </div>

        <div className="space-y-6 flex-1">
          {/* Brand Kit */}
          <div className="space-y-4">
            <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-widest flex items-center gap-2">
              <Palette className="w-3.5 h-3.5" /> Brand Kit
            </h3>
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-neutral-400">
                Primary Color
              </label>
              <div className="flex items-center gap-3">
                <div className="relative w-8 h-8 rounded-full overflow-hidden border-2 border-neutral-700 shadow-inner">
                  <input
                    type="color"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="absolute -inset-2 w-12 h-12 cursor-pointer"
                  />
                </div>
                <span className="text-sm font-mono text-neutral-400">
                  {primaryColor.toUpperCase()}
                </span>
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-neutral-400">
                Brokerage Logo
              </label>
              {logoData ? (
                <div className="relative bg-neutral-950/50 border border-neutral-800 rounded-lg p-2 flex items-center justify-between">
                  <img
                    src={logoData}
                    alt="Logo"
                    className="h-8 w-auto object-contain max-w-[150px]"
                  />
                  <button
                    onClick={removeLogo}
                    className="p-1.5 text-red-400 hover:bg-red-500/10 rounded-md transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <label className="border border-dashed border-neutral-700 bg-neutral-950/30 rounded-xl p-4 text-center cursor-pointer hover:border-indigo-500/50 hover:bg-indigo-500/5 transition-all group block">
                  <Upload className="w-5 h-5 mx-auto mb-2 text-neutral-500 group-hover:text-indigo-400 transition-colors" />
                  <span className="text-xs text-neutral-400 group-hover:text-neutral-300">
                    Upload Logo (PNG preferred)
                  </span>
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={handleLogoUpload}
                  />
                </label>
              )}
            </div>
          </div>

          <hr className="border-neutral-800/60" />

          {/* Media Settings */}
          <div className="space-y-4">
            <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-widest flex items-center gap-2">
              <Settings className="w-3.5 h-3.5" /> Media Settings
            </h3>
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-neutral-400">
                Format
              </label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value)}
                className="w-full bg-neutral-950/50 border border-neutral-800 rounded-lg p-2.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
              >
                <option>Vertical (1080x1920)</option>
                <option>Landscape (1920x1080)</option>
                <option>Square (1080x1080)</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-neutral-400">
                Language
              </label>
              <div className="flex gap-2 bg-neutral-950/50 p-1 rounded-lg border border-neutral-800">
                <button
                  onClick={() => setLanguage("English")}
                  className={`flex-1 py-1.5 text-sm rounded-md ${language === "English" ? "bg-neutral-800 text-white" : "text-neutral-400"}`}
                >
                  English
                </button>
                <button
                  onClick={() => setLanguage("Spanish")}
                  className={`flex-1 py-1.5 text-sm rounded-md ${language === "Spanish" ? "bg-neutral-800 text-white" : "text-neutral-400"}`}
                >
                  Spanish
                </button>
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-neutral-400">
                Typography Style
              </label>
              <select
                value={font}
                onChange={(e) => setFont(e.target.value)}
                className="w-full bg-neutral-950/50 border border-neutral-800 rounded-lg p-2.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
              >
                <option value="Roboto">Roboto</option>
                <option value="Inter">Inter</option>
                <option value="Cinzel">Cinzel</option>
                <option value="Playfair">Playfair Display</option>
                <option value="Prata">Prata</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-neutral-400">
                Voice Actor
              </label>
              <select
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
                className="w-full bg-neutral-950/50 border border-neutral-800 rounded-lg p-2.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
              >
                <option value="en-US-ChristopherNeural">Christopher</option>
                <option value="en-US-JennyNeural">Jenny</option>
                <option value="es-MX-JorgeNeural">Jorge</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-neutral-400">
                Background Music
              </label>
              <select
                value={music}
                onChange={(e) => setMusic(e.target.value)}
                className="w-full bg-neutral-950/50 border border-neutral-800 rounded-lg p-2.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
              >
                <option value="none">No Music</option>
                <option value="Upbeat">Upbeat</option>
                <option value="Luxury">Luxury</option>
                <option value="Motivation">Motivation</option>
              </select>
            </div>
          </div>
        </div>

        {step > 1 && !isRendering && (
          <button
            onClick={() => {
              setStep(1);
              setScenes([]);
            }}
            className="mt-auto w-full py-2.5 px-4 bg-neutral-900 border border-neutral-800 hover:bg-neutral-800 rounded-lg text-sm text-neutral-300 transition-all"
          >
            Start Over
          </button>
        )}
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 p-6 md:p-10 overflow-y-auto order-1 md:order-2 relative flex flex-col">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-indigo-500/10 blur-[120px] rounded-full pointer-events-none" />

        <div className="relative z-10 max-w-5xl mx-auto w-full">
          {!isRendering && <StepIndicator />}

          {/* RENDERING OVERLAY */}
          {isRendering && (
            <div className="flex flex-col items-center justify-center min-h-[60vh] animate-in fade-in zoom-in-95 duration-700">
              <div className="relative mb-8">
                <div className="absolute inset-0 bg-indigo-500 blur-2xl opacity-20 rounded-full animate-pulse" />
                <div className="w-24 h-24 bg-neutral-900 border-2 border-indigo-500/50 rounded-full flex items-center justify-center relative z-10">
                  <Loader2 className="w-10 h-10 text-indigo-400 animate-spin" />
                </div>
              </div>
              <h2 className="text-3xl md:text-4xl font-bold text-white mb-4 text-center">
                Rendering your video...
              </h2>
              <div className="h-8 flex items-center justify-center mb-8">
                <p
                  className="text-xl text-indigo-300 animate-pulse text-center"
                  key={renderMsgIdx}
                >
                  {RENDER_MESSAGES[renderMsgIdx]}
                </p>
              </div>
              <div className="bg-neutral-900/80 border border-neutral-800 rounded-2xl p-6 max-w-md w-full backdrop-blur-md">
                <div className="flex items-start gap-4">
                  <div className="p-3 bg-amber-500/10 rounded-xl">
                    <Clock className="w-6 h-6 text-amber-500" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-white mb-1">
                      Do not close this tab!
                    </h4>
                    <p className="text-sm text-neutral-400 leading-relaxed">
                      HD video rendering is highly demanding. This process can
                      take{" "}
                      <strong className="text-white">up to 5 minutes</strong> to
                      complete.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* STEP 1: FETCH */}
          {step === 1 && !isRendering && (
            <div className="max-w-2xl mx-auto mt-16 text-center animate-in fade-in slide-in-from-bottom-4 duration-700">
              <h2 className="text-4xl md:text-5xl font-extrabold mb-4 text-white tracking-tight">
                Automate your listings.
              </h2>
              <p className="text-lg text-neutral-400 mb-10">
                Paste a Zillow URL. We'll extract the photos, analyze the rooms,
                and build a cinematic storyboard instantly.
              </p>

              <div className="p-2 bg-neutral-900/50 backdrop-blur-md rounded-2xl border border-neutral-800 shadow-2xl flex flex-col sm:flex-row gap-2">
                <div className="relative flex-1">
                  <LinkIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-neutral-500" />
                  <input
                    type="text"
                    value={zillowUrl}
                    onChange={(e) => setZillowUrl(e.target.value)}
                    placeholder="https://www.zillow.com/homedetails/..."
                    className="w-full bg-transparent py-4 pl-12 pr-4 text-white focus:outline-none placeholder:text-neutral-600"
                  />
                </div>
                <button
                  onClick={handleFetchData}
                  disabled={isLoading || !zillowUrl}
                  className="bg-white hover:bg-neutral-200 text-black disabled:opacity-50 font-semibold py-4 px-8 rounded-xl flex items-center justify-center gap-2 transition-all w-full sm:w-auto"
                >
                  {isLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    "Generate Script"
                  )}
                </button>
              </div>

              {isLoading && (
                <div className="mt-8 flex justify-center animate-in fade-in slide-in-from-top-4 duration-500">
                  <div className="flex items-center gap-3 bg-indigo-500/10 border border-indigo-500/20 px-5 py-3 rounded-full text-sm font-medium text-indigo-300 shadow-lg shadow-indigo-500/5">
                    <Sparkles className="w-4 h-4 animate-pulse text-indigo-400" />
                    Extracting photos and running AI analysis... (approx. 15
                    sec)
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STEP 2: EDIT STORYBOARD */}
          {step === 2 && !isRendering && (
            <div className="space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700">
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div>
                  <h2 className="text-3xl font-bold text-white tracking-tight">
                    Review Storyboard
                  </h2>
                  <p className="text-neutral-400 mt-1">
                    Adjust camera movements, captions, and property details.
                  </p>
                </div>
                <button
                  onClick={handleRenderVideo}
                  disabled={isLoading || !isCompliant}
                  className="bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold py-3 px-8 rounded-xl flex items-center gap-2 transition-all shadow-lg shadow-indigo-500/25 w-full md:w-auto justify-center disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Film className="w-4 h-4" /> Render HD Video (1 Credit)
                </button>
              </div>

              <div className="bg-neutral-900/50 border border-neutral-800 rounded-2xl p-6 backdrop-blur-sm">
                <div className="mb-6 pb-6 border-b border-neutral-800/60">
                  <label className="block text-xs font-semibold text-neutral-300 uppercase tracking-wider mb-3">
                    Listing Status & Angle
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {[
                      "Coming Soon",
                      "Just Listed",
                      "For Sale",
                      "Open House",
                      "Price Reduced",
                      "Under Contract",
                      "Just Sold",
                    ].map((status) => (
                      <button
                        key={status}
                        onClick={() => setStatusChoice(status)}
                        className={`px-4 py-2 text-xs font-medium rounded-full transition-all ${statusChoice === status ? "bg-indigo-500 text-white shadow-md shadow-indigo-500/20" : "bg-neutral-950 border border-neutral-800 text-neutral-400 hover:text-neutral-200 hover:border-neutral-600"}`}
                      >
                        {status}
                      </button>
                    ))}
                  </div>
                </div>

                <h3 className="text-sm font-semibold mb-5 text-neutral-300 uppercase tracking-wider">
                  Property Details & Compliance
                </h3>

                <div className="mb-6 bg-neutral-950/50 p-4 rounded-xl border border-neutral-800">
                  <label className="block text-sm font-medium text-neutral-300 mb-3">
                    Is this your active listing?
                  </label>
                  <div className="flex gap-4">
                    <button
                      onClick={() => setIsOwnListing(true)}
                      className={`px-6 py-2 rounded-lg text-sm font-medium transition-all ${isOwnListing ? "bg-indigo-500 text-white" : "bg-neutral-900 text-neutral-400 border border-neutral-700"}`}
                    >
                      Yes, it's my listing
                    </button>
                    <button
                      onClick={() => setIsOwnListing(false)}
                      className={`px-6 py-2 rounded-lg text-sm font-medium transition-all ${!isOwnListing ? "bg-indigo-500 text-white" : "bg-neutral-900 text-neutral-400 border border-neutral-700"}`}
                    >
                      No, I'm promoting it
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                  <div>
                    <label className="block text-xs font-medium text-neutral-500 mb-1.5">
                      Your Phone (End Screen)
                    </label>
                    <input
                      type="text"
                      value={meta.phone || ""}
                      onChange={(e) =>
                        setMeta({ ...meta, phone: e.target.value })
                      }
                      placeholder="(555) 123-4567"
                      className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-2.5 text-sm focus:border-indigo-500 outline-none transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-neutral-500 mb-1.5">
                      Your Website (End Screen)
                    </label>
                    <input
                      type="text"
                      value={meta.website || ""}
                      onChange={(e) =>
                        setMeta({ ...meta, website: e.target.value })
                      }
                      placeholder="www.example.com"
                      className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-2.5 text-sm focus:border-indigo-500 outline-none transition-all"
                    />
                  </div>
                </div>

                {!isOwnListing && (
                  <div className="mb-6 p-4 border border-amber-500/30 bg-amber-500/5 rounded-xl">
                    <p className="text-xs text-amber-400 mb-4">
                      You must provide listing attribution to stay compliant
                      with local MLS rules.
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                      <div>
                        <label className="block text-xs font-medium text-neutral-500 mb-1.5">
                          Listing Agent <span className="text-red-400">*</span>
                        </label>
                        <input
                          type="text"
                          required
                          value={meta.agent}
                          onChange={(e) =>
                            setMeta({ ...meta, agent: e.target.value })
                          }
                          className="w-full bg-neutral-950 border border-amber-500/30 rounded-lg p-2.5 text-sm focus:border-amber-500 outline-none transition-all"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-neutral-500 mb-1.5">
                          Listing Brokerage{" "}
                          <span className="text-red-400">*</span>
                        </label>
                        <input
                          type="text"
                          required
                          value={meta.brokerage}
                          onChange={(e) =>
                            setMeta({ ...meta, brokerage: e.target.value })
                          }
                          className="w-full bg-neutral-950 border border-amber-500/30 rounded-lg p-2.5 text-sm focus:border-amber-500 outline-none transition-all"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-neutral-500 mb-1.5">
                          Data Source (e.g., MRED){" "}
                          <span className="text-red-400">*</span>
                        </label>
                        <input
                          type="text"
                          required
                          value={meta.mls_source}
                          onChange={(e) =>
                            setMeta({ ...meta, mls_source: e.target.value })
                          }
                          className="w-full bg-neutral-950 border border-amber-500/30 rounded-lg p-2.5 text-sm focus:border-amber-500 outline-none transition-all"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-neutral-500 mb-1.5">
                          MLS Number <span className="text-red-400">*</span>
                        </label>
                        <input
                          type="text"
                          required
                          value={meta.mls_number}
                          onChange={(e) =>
                            setMeta({ ...meta, mls_number: e.target.value })
                          }
                          className="w-full bg-neutral-950 border border-amber-500/30 rounded-lg p-2.5 text-sm focus:border-amber-500 outline-none transition-all"
                        />
                      </div>
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-6 gap-4 mb-4">
                  <div className="col-span-1 md:col-span-2">
                    <label className="block text-xs font-medium text-neutral-500 mb-1.5">
                      Property Address
                    </label>
                    <input
                      type="text"
                      value={meta.address}
                      onChange={(e) =>
                        setMeta({ ...meta, address: e.target.value })
                      }
                      className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-2.5 text-sm focus:border-indigo-500 outline-none transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-neutral-500 mb-1.5">
                      Price
                    </label>
                    <input
                      type="text"
                      value={meta.price}
                      onChange={(e) =>
                        setMeta({ ...meta, price: e.target.value })
                      }
                      className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-2.5 text-sm focus:border-indigo-500 outline-none transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-neutral-500 mb-1.5">
                      Beds
                    </label>
                    <input
                      type="text"
                      value={meta.beds}
                      onChange={(e) =>
                        setMeta({ ...meta, beds: e.target.value })
                      }
                      className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-2.5 text-sm focus:border-indigo-500 outline-none transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-neutral-500 mb-1.5">
                      Baths
                    </label>
                    <input
                      type="text"
                      value={meta.baths}
                      onChange={(e) =>
                        setMeta({ ...meta, baths: e.target.value })
                      }
                      className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-2.5 text-sm focus:border-indigo-500 outline-none transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-neutral-500 mb-1.5">
                      SqFt
                    </label>
                    <input
                      type="text"
                      value={meta.sqft}
                      onChange={(e) =>
                        setMeta({ ...meta, sqft: e.target.value })
                      }
                      className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-2.5 text-sm focus:border-indigo-500 outline-none transition-all"
                    />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {scenes.map((scene, index) => (
                  <div
                    key={scene.id}
                    className="bg-neutral-900/40 border border-neutral-800 rounded-2xl overflow-hidden hover:border-neutral-700 transition-all flex flex-col group"
                  >
                    <div className="aspect-video bg-neutral-950 flex items-center justify-center relative overflow-hidden">
                      {scene.image_url ? (
                        <img
                          src={scene.image_url}
                          alt={scene.room_type}
                          className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity duration-500 group-hover:scale-105"
                        />
                      ) : (
                        <ImageIcon className="w-8 h-8 text-neutral-700" />
                      )}
                      <div className="absolute top-3 left-3 bg-black/60 backdrop-blur-md px-2.5 py-1 rounded-md text-xs font-bold text-white shadow-sm border border-white/10">
                        {index + 1}. {scene.room_type}
                      </div>
                    </div>
                    <div className="p-5 flex flex-col gap-4 flex-1">
                      <div>
                        <label className="block text-xs font-medium text-neutral-500 mb-1.5">
                          Voiceover Script
                        </label>
                        <textarea
                          value={scene.caption}
                          onChange={(e) =>
                            updateScene(index, "caption", e.target.value)
                          }
                          className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-3 text-sm h-20 resize-none focus:border-indigo-500 outline-none transition-all"
                        />
                      </div>
                      <div className="flex items-end justify-between gap-3">
                        <div className="flex-1">
                          <label className="block text-xs font-medium text-neutral-500 mb-1.5">
                            Camera Effect
                          </label>
                          <select
                            value={scene.effect}
                            onChange={(e) =>
                              updateScene(index, "effect", e.target.value)
                            }
                            className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-2.5 text-sm focus:border-indigo-500 outline-none transition-all"
                          >
                            <option value="zoom_in">Zoom In</option>
                            <option value="drone_rise">Drone Rise</option>
                            <option value="parallax_depth">
                              Parallax Depth
                            </option>
                            <option value="slow_zoom_in">Slow Zoom In</option>
                          </select>
                        </div>
                        <div className="flex items-center gap-2 mb-2.5">
                          <label className="relative inline-flex items-center cursor-pointer">
                            <input
                              type="checkbox"
                              checked={scene.enable_vo}
                              onChange={(e) =>
                                updateScene(
                                  index,
                                  "enable_vo",
                                  e.target.checked,
                                )
                              }
                              className="sr-only peer"
                            />
                            <div className="w-9 h-5 bg-neutral-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-500"></div>
                            <span className="ml-2 text-xs font-medium text-neutral-400">
                              VO
                            </span>
                          </label>
                        </div>
                      </div>
                      <div className="flex gap-1.5 mt-auto pt-4 border-t border-neutral-800/60">
                        <button
                          onClick={() => moveScene(index, "up")}
                          disabled={index === 0}
                          className="p-2 text-neutral-500 hover:text-white hover:bg-neutral-800 rounded-lg disabled:opacity-30 transition-colors"
                        >
                          <ArrowUp className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => moveScene(index, "down")}
                          disabled={index === scenes.length - 1}
                          className="p-2 text-neutral-500 hover:text-white hover:bg-neutral-800 rounded-lg disabled:opacity-30 transition-colors"
                        >
                          <ArrowDown className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => removeScene(index)}
                          className="p-2 text-red-400 hover:bg-red-500/10 rounded-lg ml-auto flex items-center gap-1.5 text-xs font-medium transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" /> Remove
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* STEP 3: RESULT */}
          {step === 3 && videoUrl && !isRendering && (
            <div className="max-w-4xl mx-auto mt-10 animate-in fade-in zoom-in-95 duration-700">
              <div className="text-center mb-8">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-500/10 mb-4">
                  <CheckCircle2 className="w-8 h-8 text-emerald-500" />
                </div>
                <h2 className="text-3xl font-bold text-white tracking-tight">
                  Render Complete
                </h2>
              </div>

              <div
                className={`bg-black rounded-3xl overflow-hidden ring-1 ring-white/10 shadow-2xl shadow-indigo-500/10 mb-8 relative group max-h-[70vh] mx-auto flex justify-center ${
                  format.includes("Vertical")
                    ? "aspect-[9/16] w-auto"
                    : format.includes("Square")
                      ? "aspect-square w-full max-w-2xl"
                      : "aspect-video w-full"
                }`}
              >
                <video
                  src={videoUrl}
                  controls
                  className="w-full h-full object-contain"
                  autoPlay
                />
              </div>

              <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
                <div className="w-full sm:w-auto flex flex-col items-center">
                  <button
                    onClick={handleForceDownload}
                    disabled={isDownloading}
                    className="flex items-center justify-center gap-2 bg-white hover:bg-neutral-200 text-black font-semibold py-3.5 px-8 rounded-xl transition-all shadow-lg w-full sm:w-auto disabled:opacity-80 relative overflow-hidden"
                  >
                    {isDownloading && (
                      <div
                        className="absolute left-0 top-0 bottom-0 bg-indigo-500/20 transition-all duration-300 ease-out"
                        style={{ width: `${downloadProgress}%` }}
                      />
                    )}
                    <span className="relative flex items-center gap-2 z-10">
                      {isDownloading ? (
                        <>
                          <Loader2 className="w-5 h-5 animate-spin" />{" "}
                          {downloadProgress}%
                        </>
                      ) : (
                        <>
                          <Download className="w-5 h-5" /> Download MP4
                        </>
                      )}
                    </span>
                  </button>
                </div>
                <button className="flex items-center justify-center gap-2 bg-[#1877F2] hover:bg-[#166fe5] text-white font-semibold py-3.5 px-8 rounded-xl transition-all shadow-lg shadow-[#1877F2]/20 w-full sm:w-auto">
                  <Share2 className="w-5 h-5" /> Post to Facebook
                </button>
              </div>
              <div className="mt-12 bg-neutral-900/50 p-6 rounded-2xl border border-neutral-800 backdrop-blur-sm">
                <h3 className="text-sm font-semibold mb-3 text-neutral-300 flex items-center gap-2">
                  <span>📝</span> Suggested Post Copy
                </h3>
                <textarea
                  readOnly
                  value={fbDraft}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-xl p-4 text-sm h-28 resize-none text-neutral-400 focus:outline-none focus:border-indigo-500 transition-colors leading-relaxed"
                />
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
