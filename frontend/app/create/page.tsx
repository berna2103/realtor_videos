"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Settings,
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
  Film,
  Coins,
  AlertCircle,
  Volume2,
  X,
  LogOut,
  Globe,
  Phone,
  RefreshCw,
  LayoutDashboard,
} from "lucide-react";

import { useAuth } from "../../context/AuthContext";
import { supabase } from "../../lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const STRIPE_PRICE_ID_5_CREDITS =
  process.env.NEXT_PUBLIC_STRIPE_PRICE_ID || "price_XXXXXX";

// Expanded Voice Options to include Spanish High-Quality Neural Voices
const VOICE_OPTIONS = [
  { label: "Professional (Male)", value: "Professional/Clean" },
  { label: "Luxury (Male)", value: "Deep/Luxury" },
  { label: "Friendly (Male)", value: "Friendly/Fast" },
  { label: "Warm (Female)", value: "Female/Warm" },
  { label: "Español MX (Hombre)", value: "Spanish/Mexico-Male" },
  { label: "Español MX (Mujer)", value: "Spanish/Mexico-Female" },
  { label: "Español ES (Hombre)", value: "Spanish/Spain-Male" },
  { label: "Español US (Hombre)", value: "Spanish/US-Male" },
];

const EFFECT_OPTIONS = [
  { label: "Auto / Random (Recommended)", value: "auto" },
  { label: "Slow Zoom In", value: "zoom_in" },
  { label: "Slow Zoom Out", value: "zoom_out" },
  { label: "Pan Left", value: "pan_left" },
  { label: "Pan Right", value: "pan_right" },
  { label: "Pan Up", value: "pan_up" },
  { label: "Pan Down", value: "pan_down" },
  { label: "Pan Up-Left (Diagonal)", value: "pan_up_left" },
  { label: "Pan Down-Right (Diagonal)", value: "pan_down_right" },
  { label: "3D Perspective Pan Right", value: "3d_pan_right" },
  { label: "3D Perspective Pan Left", value: "3d_pan_left" },
  { label: "Drone Push (Bank Right)", value: "drone_push" },
  { label: "Drone Pull (Bank Left)", value: "drone_pull" },
  { label: "Luxury Breathe (Cinematic Ease)", value: "luxury_breathe" },
];

const VOICE_PREVIEWS: Record<string, string> = {
  "Professional/Clean": "/previews/andrew_professional.mp3",
  "Deep/Luxury": "/previews/eric_luxury.mp3",
  "Friendly/Fast": "/previews/guy_friendly.mp3",
  "Female/Warm": "/previews/ava_warm.mp3",
  "Spanish/Mexico-Male": "/previews/jorge_mexico.mp3",
};

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
  custom_cta?: string;
  custom_end_title?: string;
}

const RENDER_MESSAGES = [
  "Spinning up the render engine...",
  "Generating AI voiceovers...",
  "Applying cinematic camera movements...",
  "Stitching video frames...",
  "Mixing the audio tracks...",
  "Almost there! Please don't close this tab...",
];

// --- STABLE SIDEBAR COMPONENT ---
const SidebarSettings = ({
  primaryColor,
  setPrimaryColor,
  meta,
  setMeta,
  logoData,
  setLogoData,
  handleLogoUpload,
  voice,
  setVoice,
  isPreviewing,
  playPreview,
  format,
  setFormat,
  font,
  setFont,
  music,
  setMusic,
  language,
  setLanguage,
  user,
  isAuthLoading,
  showCaptions, 
  setShowCaptions, 
  enableVoice, 
  setEnableVoice,   
  enableMusic, 
  setEnableMusic,
  saveBrandKit
}: any) => (
  <div className="space-y-10">
    <section className="space-y-6">
      <h3 className="text-[11px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 pb-2 flex items-center gap-2">
        <Palette className="w-3.5 h-3.5" /> Branding & Leads
      </h3>
      <div className="space-y-5">
        <div className="flex items-center justify-between bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-xs font-semibold text-slate-600">
            Theme Color
          </span>
          <input
            type="color"
            value={primaryColor}
            onChange={(e) => setPrimaryColor(e.target.value)}
            className="w-8 h-8 rounded-full bg-transparent border-none cursor-pointer p-0 appearance-none shadow-inner"
          />
        </div>

        <div className="space-y-2">
          <label className="text-[11px] text-slate-500 font-bold uppercase ml-1 block">
            Agent Website
          </label>
          <div className="relative">
            <Globe className="absolute left-3.5 top-3.5 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="www.luxuryhomes.com"
              value={meta.website}
              onChange={(e) => setMeta({ ...meta, website: e.target.value })}
              className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3.5 pl-10 text-sm text-slate-900 outline-none focus:border-blue-500 focus:bg-white transition-all shadow-sm"
            />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-[11px] text-slate-500 font-bold uppercase ml-1 block">
            Lead Line
          </label>
          <div className="relative">
            <Phone className="absolute left-3.5 top-3.5 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="(555) 000-0000"
              value={meta.phone}
              onChange={(e) => setMeta({ ...meta, phone: e.target.value })}
              className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3.5 pl-10 text-sm text-slate-900 outline-none focus:border-blue-500 focus:bg-white transition-all shadow-sm"
            />
          </div>
        </div>
        <div className="space-y-2">
          <label className="text-[11px] text-slate-500 font-bold uppercase ml-1 block">
            Custom Call-to-Action (Optional)
          </label>
          <input
            type="text"
            placeholder="e.g., OPEN HOUSE SUNDAY!"
            value={meta.custom_cta || ""}
            onChange={(e) => setMeta({ ...meta, custom_cta: e.target.value })}
            className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-sm"
          />
        </div>

        <div className="space-y-3">
          <span className="text-[11px] text-slate-500 font-bold uppercase ml-1 block">
            Brokerage Logo
          </span>
          {logoData ? (
            <div className="relative group rounded-2xl overflow-hidden bg-white border border-slate-200 p-6 shadow-md flex items-center justify-center min-h-[100px] transition-all">
              <img
                src={logoData}
                className="max-h-14 w-auto object-contain"
                alt="Logo preview"
              />
              <button
                onClick={() => setLogoData(null)}
                className="absolute top-3 right-3 p-1.5 bg-red-50 text-red-500 rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-100"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <label className="flex flex-col items-center justify-center border-2 border-dashed border-slate-200 bg-slate-50 py-8 rounded-2xl hover:border-blue-400 hover:bg-white transition-all cursor-pointer group">
              <Upload className="w-6 h-6 text-slate-400 group-hover:text-blue-600 mb-2 transition-colors" />
              <span className="text-xs font-bold text-slate-600">
                Upload PNG
              </span>
              <input
                type="file"
                accept="image/*"
                onChange={handleLogoUpload}
                className="hidden"
              />
            </label>
          )}
        </div>

        {/* ENHANCEMENT: Save Brand Kit */}
        <button
          onClick={saveBrandKit}
          className="w-full mt-2 py-3 bg-slate-100 text-slate-700 text-xs font-bold rounded-xl hover:bg-slate-200 transition-colors flex items-center justify-center gap-2"
        >
          <Settings className="w-4 h-4" /> Save as Default Brand
        </button>

      </div>
    </section>

    <section className="space-y-6">
      <h3 className="text-[11px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 pb-2 flex items-center gap-2">
        <Settings className="w-3.5 h-3.5" /> Media Settings
      </h3>
      <div className="space-y-2">
        <label className="text-[11px] text-slate-500 font-bold uppercase ml-1 block">
          Master Overrides
        </label>
        <div className="grid grid-cols-3 gap-2">
          <button 
            onClick={() => setShowCaptions(!showCaptions)} 
            className={`py-2 rounded-xl text-[10px] font-bold uppercase tracking-wider transition-all border ${showCaptions ? 'bg-slate-900 text-white border-slate-900 shadow-md' : 'bg-slate-50 text-slate-400 border-slate-200 hover:border-slate-300'}`}
          >
            Captions {showCaptions ? 'ON' : 'OFF'}
          </button>
          
          <button 
            onClick={() => setEnableVoice(!enableVoice)} 
            className={`py-2 rounded-xl text-[10px] font-bold uppercase tracking-wider transition-all border ${enableVoice ? 'bg-slate-900 text-white border-slate-900 shadow-md' : 'bg-slate-50 text-slate-400 border-slate-200 hover:border-slate-300'}`}
          >
            Voice {enableVoice ? 'ON' : 'OFF'}
          </button>
          
          <button 
            onClick={() => setEnableMusic(!enableMusic)} 
            className={`py-2 rounded-xl text-[10px] font-bold uppercase tracking-wider transition-all border ${enableMusic ? 'bg-slate-900 text-white border-slate-900 shadow-md' : 'bg-slate-50 text-slate-400 border-slate-200 hover:border-slate-300'}`}
          >
            Music {enableMusic ? 'ON' : 'OFF'}
          </button>
        </div>
      </div>
      <div className="space-y-5">
        <div className="space-y-2">
          <label className="text-[11px] text-slate-500 font-bold uppercase ml-1 block">
            Aspect Ratio
          </label>
          <select
            value={format}
            onChange={(e) => setFormat(e.target.value)}
            className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-sm text-slate-900 font-medium outline-none hover:border-slate-400 transition-colors"
          >
            <option>Vertical (Tik Tok, Reels, Shorts)</option>
            <option>Landscape (YouTube)</option>
            <option>Square (Facebook or Instagram Posts)</option>
          </select>
        </div>

        <div className="space-y-2">
          <label className="text-[11px] text-slate-500 font-bold uppercase ml-1 block">
            Narrator & Voice
          </label>
          <div className="flex flex-col gap-3">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-sm text-slate-900 font-medium outline-none"
            >
              <option>English</option>
              <option>Spanish</option>
            </select>
            <div className="flex gap-2">
              <select
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
                className="flex-1 bg-slate-50 border border-slate-200 rounded-xl p-3 text-sm text-slate-900 font-medium outline-none"
              >
                {VOICE_OPTIONS.map((v) => (
                  <option key={v.value} value={v.value}>
                    {v.label}
                  </option>
                ))}
              </select>
              <button
                onClick={playPreview}
                className="p-3 bg-slate-900 text-white rounded-xl shadow-lg hover:bg-black transition-all active:scale-95 flex items-center justify-center"
              >
                {isPreviewing ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Volume2 className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-[11px] text-slate-500 font-bold uppercase ml-1 block">
            Typography
          </label>
          <select
            value={font}
            onChange={(e) => setFont(e.target.value)}
            className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-sm text-slate-900 font-medium outline-none"
          >
            <option value="Inter">Inter</option>
            <option value="Roboto">Roboto</option>
            <option value="Cinzel">Cinzel</option>
            <option value="Playfair">Playfair Display</option>
          </select>
        </div>

        <div className="space-y-2">
          <label className="text-[11px] text-slate-500 font-bold uppercase ml-1 block">
            Soundtrack
          </label>
          <select
            value={music}
            onChange={(e) => setMusic(e.target.value)}
            className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-sm text-slate-900 font-medium outline-none"
          >
            <option value="none">No Music</option>
            <option value="Upbeat">Upbeat</option>
            <option value="Luxury">Luxury</option>
            <option value="Motivation">Motivation</option>
          </select>
        </div>
      </div>
    </section>

    {user && (
      <div className="pt-8 border-t border-slate-100">
        {!isAuthLoading && user && (
          <Link
            href="/dashboard"
            className="flex items-center gap-2 bg-white border border-slate-200 px-4 py-2 rounded-xl hover:bg-slate-50 transition-all"
          >
            <Film className="w-4 h-4 text-blue-600" />
            <span className="font-bold text-slate-700">My Video Library</span>
          </Link>
        )}
      </div>
    )}
  </div>
);

export default function CinematicListingApp() {
  const {
    user,
    email: userEmail,
    credits,
    signOut,
    refreshCredits,
    isLoading: isAuthLoading,
  } = useAuth();

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
  const [scenes, setScenes] = useState<Scene[]>([]);
  
  // ENHANCEMENT: Multi-platform Social Drafts
  const [socialDrafts, setSocialDrafts] = useState({ facebook: "", instagram: "", tiktok: "" });
  const [activeTab, setActiveTab] = useState("instagram");
  const [renderProgress, setRenderProgress] = useState(0);

  const [showClearConfirmModal, setShowClearConfirmModal] = useState(false);
  const [showCaptions, setShowCaptions] = useState(true);
  const [enableVoice, setEnableVoice] = useState(true);
  const [enableMusic, setEnableMusic] = useState(true);

  const [showAuthModal, setShowAuthModal] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [isOwnListing, setIsOwnListing] = useState<boolean>(true);
  const [showTopUpModal, setShowTopUpModal] = useState(false);
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [isLoading, setIsLoading] = useState(false);
  const [zillowUrl, setZillowUrl] = useState("");
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(false);
  const [renderMsgIdx, setRenderMsgIdx] = useState(0);

  const [format, setFormat] = useState("Vertical (1080x1920)");
  const [language, setLanguage] = useState("English");
  const [voice, setVoice] = useState("Professional/Clean");
  const [font, setFont] = useState("Montserrat");
  const [music, setMusic] = useState("Upbeat");
  const [primaryColor, setPrimaryColor] = useState("#006aff");
  const [logoData, setLogoData] = useState<string | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [statusChoice, setStatusChoice] = useState("Just Listed");
  const [isDownloading, setIsDownloading] = useState(false);

  // Mobile UI States
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  // Sync Voice and Language for Spanish
  useEffect(() => {
    if (language === "Spanish" && !voice.startsWith("Spanish/")) {
      setVoice("Spanish/Mexico-Male");
    } else if (language === "English" && voice.startsWith("Spanish/")) {
      setVoice("Professional/Clean");
    }
  }, [language]);

  useEffect(() => {
    const savedMeta = localStorage.getItem("draft_meta");
    const savedScenes = localStorage.getItem("draft_scenes");
    const savedBrand = localStorage.getItem("realtor_brand_kit");

    // ENHANCEMENT: Pre-fill the Brand Kit
    if (savedBrand) {
      const parsed = JSON.parse(savedBrand);
      setMeta(prev => ({
        ...prev,
        agent: parsed.agent || "",
        brokerage: parsed.brokerage || "",
        phone: parsed.phone || "",
        website: parsed.website || ""
      }));
      if (parsed.primaryColor) setPrimaryColor(parsed.primaryColor);
      if (parsed.logoData) setLogoData(parsed.logoData);
    }

    if (savedMeta) setMeta(prev => ({ ...prev, ...JSON.parse(savedMeta) }));
    if (savedScenes) setScenes(JSON.parse(savedScenes));
  }, []);

  useEffect(() => {
    if (scenes.length > 0 || meta.address !== "") {
      localStorage.setItem("draft_meta", JSON.stringify(meta));
      localStorage.setItem("draft_scenes", JSON.stringify(scenes));
    }
  }, [meta, scenes]);

  const saveBrandKit = () => {
    const brandData = {
      agent: meta.agent,
      brokerage: meta.brokerage,
      phone: meta.phone,
      website: meta.website,
      primaryColor: primaryColor,
      logoData: logoData
    };
    localStorage.setItem("realtor_brand_kit", JSON.stringify(brandData));
    alert("✅ Brand preferences saved as default!");
  };

  const isCompliant =
    isOwnListing ||
    (meta.agent && meta.brokerage && meta.mls_source && meta.mls_number);

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
      }
    } catch (error: any) {
      alert(error.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleBuyCredits = async () => {
    if (!user) return setShowAuthModal(true);
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userId: user.id,
          priceId: STRIPE_PRICE_ID_5_CREDITS,
        }),
      });
      const data = await res.json();
      if (data.url) window.location.href = data.url;
    } catch (e) {
      alert("Checkout failed");
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

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to fetch property data");
      }

      setMeta({ ...meta, ...data.meta });
      // ENHANCEMENT: Populate Social Drafts
      setSocialDrafts(data.socialDrafts || { facebook: data.fbDraft || "", instagram: "", tiktok: "" });
      setScenes(data.scenes || []);
      setStep(2);
    } catch (error: any) {
      console.error("Fetch error:", error);
      alert(`Fetch failed: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRenderVideo = async () => {
    if (!user) {
      setShowAuthModal(true);
      return;
    }

    if (credits !== null && credits < 1) {
      setShowTopUpModal(true);
      return;
    }

    setIsRendering(true);
    setRenderProgress(0);
    setRenderMsgIdx(0);
    const msgInterval = setInterval(
      () => setRenderMsgIdx((p) => (p + 1) % RENDER_MESSAGES.length),
      8000,
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
          music: enableMusic ? music : "none",
          status_choice: statusChoice,
          primary_color: primaryColor,
          logo_data: logoData,
          is_own_listing: isOwnListing, 
          custom_cta: meta.custom_cta || null,
          show_captions: showCaptions,
          enable_voice: enableVoice,
        }),
      });

      if (res.status === 402) {
        clearInterval(msgInterval);
        setIsRendering(false);
        setShowTopUpModal(true);
        return; 
      }

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to start render job.");
      }

      const data = await res.json();
      refreshCredits();

      const poll = setInterval(async () => {
        try {
          const sRes = await fetch(`${API_URL}/api/job-status/${data.job_id}`);
          const sData = await sRes.json();
          
          // ENHANCEMENT: Update rendering progress explicitly 
          if (sData.progress) {
            setRenderProgress(sData.progress);
          }

          if (sData.status === "completed") {
            clearInterval(poll);
            clearInterval(msgInterval);
            setVideoUrl(sData.video_url);
            setIsRendering(false);
            setRenderProgress(0);
            setStep(3);

            localStorage.removeItem("draft_meta");
            localStorage.removeItem("draft_scenes");
          } else if (sData.status === "failed") {
            clearInterval(poll);
            clearInterval(msgInterval);
            setIsRendering(false);
            setRenderProgress(0);
            alert(`Render failed: ${sData.error || "Unknown error"}`);
          }
        } catch (err) {
          console.error("Polling error", err);
        }
      }, 3000);
    } catch (e: any) {
      clearInterval(msgInterval);
      setIsRendering(false);
      setRenderProgress(0);
      alert(
        e.message ||
          "Network error. Could not connect to the rendering engine.",
      );
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
      a.download = `${meta.address.replace(/[^a-z0-9]/gi, "_") || "video"}.mp4`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (e) {
      window.open(videoUrl, "_blank");
    } finally {
      setIsDownloading(false);
    }
  };

  const handleStartOver = () => {
    setShowClearConfirmModal(true);
  };

  const executeStartOver = () => {
    localStorage.removeItem("draft_meta");
    localStorage.removeItem("draft_scenes");
    window.location.reload();
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

  return (
    <div className="min-h-screen bg-[#F9FAFB] text-slate-900 font-sans flex flex-col overflow-hidden">
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
                Secure Your Work
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
                {authLoading ? "Authenticating..." : "Log In & Render"}
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

      {/* --- TOP NAVIGATION --- */}
      <nav className="h-20 border-b border-slate-200 bg-white/80 backdrop-blur-xl flex items-center justify-between px-4 sm:px-8 z-30 relative">
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
              <button
                onClick={() => setShowTopUpModal(true)}
                className="ml-1 sm:ml-2 text-[10px] sm:text-[11px] bg-blue-600 text-white px-2.5 sm:px-3 py-1 rounded-full font-bold hover:bg-blue-700 transition-colors"
              >
                Buy
              </button>
            </div>
          )}

          {user ? (
            <div className="flex items-center gap-1 sm:gap-4 shrink-0">
              <Link
                href="/dashboard"
                className="lg:hidden p-1.5 sm:p-2 text-slate-400 hover:text-blue-600 transition-colors"
              >
                <LayoutDashboard className="w-5 h-5" />
              </Link>

              <span className="text-sm text-slate-500 hidden md:block font-medium">
                {userEmail}
              </span>

              <button
                onClick={signOut}
                className="p-1.5 sm:p-2 text-slate-400 hover:text-red-500 transition-colors"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowAuthModal(true)}
              className="text-xs sm:text-sm font-bold text-blue-600 hover:text-blue-700 px-4 sm:px-6 py-2 sm:py-2.5 rounded-full border border-blue-100 bg-blue-50/50 transition-all shrink-0"
            >
              Sign In
            </button>
          )}
        </div>
      </nav>

      {/* --- MAIN APP LAYOUT (DESKTOP) --- */}
      <div className="flex flex-1 overflow-hidden relative w-full">
        {/* DESKTOP ONLY: Left Sidebar */}
        <aside className="hidden lg:flex w-80 border-r border-slate-200 flex-col bg-white overflow-y-auto p-8 gap-8 custom-scrollbar flex-shrink-0 relative z-10">
          <SidebarSettings
            primaryColor={primaryColor}
            setPrimaryColor={setPrimaryColor}
            meta={meta}
            setMeta={setMeta}
            logoData={logoData}
            setLogoData={setLogoData}
            handleLogoUpload={(e: any) => {
              const file = e.target.files?.[0];
              if (file) {
                const reader = new FileReader();
                reader.onloadend = () => setLogoData(reader.result as string);
                reader.readAsDataURL(file);
              }
            }}
            voice={voice}
            setVoice={setVoice}
            isPreviewing={isPreviewing}
            playPreview={() => {
              const audioUrl = VOICE_PREVIEWS[voice];
              if (!audioUrl) return;
              setIsPreviewing(true);
              const audio = new Audio(audioUrl);
              audio.play().catch(() => setIsPreviewing(false));
              audio.onended = () => setIsPreviewing(false);
            }}
            format={format}
            setFormat={setFormat}
            font={font}
            setFont={setFont}
            music={music}
            setMusic={setMusic}
            language={language}
            setLanguage={setLanguage}
            user={user}
            isAuthLoading={isAuthLoading}
            showCaptions={showCaptions}
            setShowCaptions={setShowCaptions}
            enableVoice={enableVoice}
            setEnableVoice={setEnableVoice}
            enableMusic={enableMusic}
            setEnableMusic={setEnableMusic}
            saveBrandKit={saveBrandKit}
          />
          {step > 1 && (
            <button
              onClick={handleStartOver}
              className="mt-auto flex items-center justify-center gap-2 p-4 bg-red-50 border border-red-100 rounded-xl text-xs font-bold text-red-600 hover:bg-red-100 transition-all"
            >
              <RefreshCw className="w-3 h-3" /> Clear Storyboard
            </button>
          )}
        </aside>

        {/* MAIN CONTENT AREA */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-8 lg:p-12 pb-32 lg:pb-12 bg-[#F9FAFB] custom-scrollbar relative z-0">
          {isRendering ? (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
              <div className="relative mb-10">
                <div className="absolute inset-0 bg-blue-500/20 blur-3xl rounded-full animate-pulse"></div>
                <Loader2 className="w-16 h-16 text-blue-600 animate-spin relative z-10" />
              </div>
              <h2 className="font-serif text-4xl font-bold text-slate-900 mb-3 tracking-tight">
                Finishing Your Tour
              </h2>
              <p className="font-serif text-xl font-bold text-slate-600 mb-3 tracking-tight">
                This may take up to 5 minutes.
              </p>
              <p className="text-slate-500 font-medium text-lg max-w-sm mx-auto mb-8">
                {RENDER_MESSAGES[renderMsgIdx]}
              </p>
              
              {/* ENHANCEMENT: Rendering Progress Bar */}
              <div className="w-full max-w-md mx-auto mt-8">
                <div className="flex justify-between text-xs font-bold text-slate-500 mb-2">
                  <span>Rendering Engine</span>
                  <span>{renderProgress}%</span>
                </div>
                <div className="h-3 w-full bg-slate-200 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-blue-600 rounded-full transition-all duration-500 ease-out relative overflow-hidden"
                    style={{ width: `${renderProgress}%` }}
                  >
                    <div className="absolute top-0 left-0 bottom-0 right-0 bg-gradient-to-r from-transparent via-white/30 to-transparent -translate-x-full animate-[shimmer_1.5s_infinite]" />
                  </div>
                </div>
              </div>

            </div>
          ) : step === 1 ? (
            <div className="max-w-4xl mx-auto py-24 text-center">
              <span className="inline-block px-4 py-1.5 bg-blue-50 text-blue-700 rounded-full text-xs font-black uppercase tracking-widest mb-6">
                AI Video for Real Estate
              </span>
              <h2 className="font-serif text-6xl md:text-8xl font-bold text-slate-900 mb-8 leading-[1.05] tracking-tight">
                Real Estate <br />{" "}
                <span className="text-slate-400 italic font-medium">
                  Made Cinematic.
                </span>
              </h2>
              <p className="text-slate-500 text-xl mb-12 max-w-2xl mx-auto leading-relaxed">
                Transform any Zillow listing into a high-end property tour in
                seconds. Paste the URL below to begin.
              </p>
              <div className="p-3 bg-white border border-slate-200 rounded-[2rem] flex flex-col sm:flex-row gap-3 shadow-2xl shadow-slate-200/60 ring-1 ring-black/5 max-w-3xl mx-auto">
                <div className="flex-1 flex items-center px-4">
                  <LinkIcon className="w-5 h-5 text-slate-400 mr-3" />
                  <input
                    type="text"
                    value={zillowUrl}
                    onChange={(e) => setZillowUrl(e.target.value)}
                    placeholder="Paste Zillow URL here..."
                    className="w-full bg-transparent py-4 text-slate-900 outline-none placeholder:text-slate-400 text-lg"
                  />
                </div>
                <button
                  onClick={handleFetchData}
                  className="bg-blue-600 text-white px-10 py-5 rounded-2xl font-bold hover:bg-blue-700 transition-all shadow-lg hover:shadow-blue-200 active:scale-[0.98] flex items-center justify-center"
                >
                  {isLoading ? (
                    <Loader2 className="animate-spin" />
                  ) : (
                    "Build My Tour"
                  )}
                </button>
              </div>
            </div>
          ) : step === 2 ? (
            <div className="max-w-5xl mx-auto space-y-12">
              <header className="flex flex-col items-center text-center gap-6">
                <div>
                  <h2 className="font-serif text-4xl sm:text-5xl font-bold text-slate-900 tracking-tight">
                    Storyboard
                  </h2>
                  <p className="text-slate-500 text-lg mt-1 font-medium">
                    Customize your cinematic narrative.
                  </p>
                </div>

                <div className="flex flex-wrap justify-center gap-2 bg-white p-1.5 rounded-2xl border border-slate-200 shadow-sm w-fit mx-auto">
                  {[
                    "Home For Sale",
                    "Coming Soon",
                    "Just Listed",
                    "Under Contract",
                    "Open House",
                    "Price Reduced",
                    "Just Sold",
                  ].map((s) => (
                    <button
                      key={s}
                      onClick={() => setStatusChoice(s)}
                      className={`px-5 py-2.5 rounded-xl text-[11px] font-bold uppercase tracking-wider transition-all ${
                        statusChoice === s
                          ? "bg-slate-900 text-white shadow-lg"
                          : "text-slate-500 hover:bg-slate-50"
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </header>

              <div className="grid gap-8">
                {scenes.map((s, i) => (
                  <div
                    key={i}
                    className="bg-white border border-slate-200 rounded-[2rem] p-4 sm:p-8 flex flex-col gap-6 group hover:border-blue-500/30 hover:shadow-xl transition-all duration-500"
                  >
                    <div className="w-full aspect-video bg-slate-100 rounded-2xl overflow-hidden relative shadow-inner flex-shrink-0">
                      <img
                        src={s.image_url}
                        className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                        alt="Scene preview"
                      />
                      <div className="absolute top-4 left-4 bg-white/90 backdrop-blur-md px-3 py-1.5 rounded-full text-[10px] font-black text-slate-900 shadow-sm border border-slate-100">
                        SCENE {i + 1}
                      </div>
                    </div>

                    <div className="flex-1 flex flex-col gap-5">
                      <div className="relative">
                        <textarea
                          value={s.caption}
                          onChange={(e) =>
                            updateScene(i, "caption", e.target.value)
                          }
                          className="w-full bg-slate-50 border border-slate-100 rounded-2xl p-5 text-slate-800 text-base leading-relaxed outline-none focus:ring-2 focus:ring-blue-500/10 focus:border-blue-500/50 resize-none h-28 transition-all"
                        />
                      </div>
                      <div className="flex flex-wrap items-center justify-between gap-4">
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-widest hidden sm:inline">
                            Effect:
                          </span>
                          <select
                            value={s.effect}
                            onChange={(e) =>
                              updateScene(i, "effect", e.target.value)
                            }
                            className="bg-white border border-slate-200 rounded-xl px-4 py-2 text-sm text-slate-700 font-medium outline-none hover:border-slate-300 transition-colors"
                          >
                            {EFFECT_OPTIONS.map((opt) => (
                              <option key={opt.value} value={opt.value}>
                                {opt.label}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => moveScene(i, "up")}
                            disabled={i === 0}
                            className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-400 hover:text-slate-900 disabled:opacity-30 transition-all active:scale-90"
                          >
                            <ArrowUp className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => moveScene(i, "down")}
                            disabled={i === scenes.length - 1}
                            className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-400 hover:text-slate-900 disabled:opacity-30 transition-all active:scale-90"
                          >
                            <ArrowDown className="w-4 h-4" />
                          </button>
                          <div className="w-[1px] h-6 bg-slate-200 mx-1" />
                          <button
                            onClick={() =>
                              setScenes(scenes.filter((_, idx) => idx !== i))
                            }
                            className="p-3 bg-red-50 text-red-400 border border-red-100 rounded-xl hover:bg-red-500 hover:text-white transition-all active:scale-90"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="hidden lg:block fixed bottom-10 left-1/2 -translate-x-1/2 z-40 w-full max-w-sm px-6">
                <button
                  onClick={handleRenderVideo}
                  disabled={!isCompliant}
                  className="w-full bg-slate-900 hover:bg-black text-white py-6 rounded-[2rem] font-bold text-sm shadow-2xl flex items-center justify-center gap-3 disabled:opacity-40 transition-all active:scale-[0.97] group"
                >
                  <Film className="w-5 h-5 text-blue-400 group-hover:rotate-12 transition-transform" />{" "}
                  Create Full HD Video
                </button>
                {!isCompliant && (
                  <div className="mt-4 flex items-center justify-center gap-2 bg-white/90 backdrop-blur border border-red-100 px-4 py-2 rounded-full shadow-lg">
                    <AlertCircle className="w-3.5 h-3.5 text-red-500" />
                    <p className="text-[11px] text-red-600 font-bold uppercase tracking-tighter">
                      Missing Brokerage Info
                    </p>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="max-w-xl mx-auto py-12 text-center">
              <div className="w-20 h-20 bg-emerald-50 rounded-3xl flex items-center justify-center mx-auto mb-8 shadow-inner">
                <CheckCircle2 className="w-10 h-10 text-emerald-500 drop-shadow-md" />
              </div>
              <h2 className="font-serif text-4xl sm:text-5xl font-bold text-slate-900 mb-4 tracking-tight">
                Masterpiece Ready
              </h2>
              <p className="text-slate-500 mb-10 font-medium">
                Your cinematic property tour is ready for the market.
              </p>
              <div className="aspect-[9/16] bg-slate-950 rounded-[3rem] overflow-hidden mb-10 shadow-2xl ring-[12px] ring-white">
                <video
                  src={videoUrl!}
                  controls
                  autoPlay
                  className="w-full h-full"
                />
              </div>
              <div className="flex flex-col gap-4">
                <button
                  onClick={handleForceDownload}
                  disabled={isDownloading}
                  className="w-full bg-slate-900 text-white py-5 rounded-2xl font-bold flex items-center justify-center gap-3 hover:bg-black transition-all shadow-xl active:scale-[0.98]"
                >
                  {isDownloading ? (
                    <Loader2 className="animate-spin w-5 h-5" />
                  ) : (
                    <Download className="w-5 h-5 text-blue-400" />
                  )}{" "}
                  Download 4K MP4
                </button>

                {/* ENHANCEMENT: Multi-Platform Social Drafts Panel */}
                <div className="bg-white border border-slate-200 rounded-2xl p-4 text-left mt-2 shadow-sm">
                  <div className="flex gap-2 mb-3">
                    {['instagram', 'tiktok', 'facebook'].map(platform => (
                      <button 
                        key={platform}
                        onClick={() => setActiveTab(platform)}
                        className={`text-[11px] font-bold px-4 py-2 rounded-full capitalize transition-colors ${activeTab === platform ? 'bg-blue-100 text-blue-700' : 'bg-slate-50 text-slate-500 hover:bg-slate-100'}`}
                      >
                        {platform}
                      </button>
                    ))}
                  </div>
                  <textarea 
                    readOnly
                    value={socialDrafts[activeTab as keyof typeof socialDrafts]} 
                    className="w-full h-28 text-sm bg-slate-50 border border-slate-100 rounded-xl p-3 resize-none outline-none text-slate-700 custom-scrollbar"
                  />
                  <div className="flex justify-between items-center mt-3">
                    <button 
                      onClick={() => {
                        navigator.clipboard.writeText(socialDrafts[activeTab as keyof typeof socialDrafts]);
                        alert(`✅ ${activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} caption copied!`);
                      }}
                      className="text-[11px] text-blue-600 font-bold hover:underline"
                    >
                      Copy Caption
                    </button>
                    {activeTab === 'facebook' && (
                      <button
                        onClick={() => window.open(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(videoUrl!)}`, "_blank", "width=600,height=500")}
                        className="text-[11px] bg-[#1877F2] text-white px-3 py-1.5 rounded-lg font-bold hover:bg-[#166fe5] transition-colors flex items-center gap-1.5"
                      >
                         <Share2 className="w-3 h-3" /> Post to FB
                      </button>
                    )}
                  </div>
                </div>

                <button
                  onClick={() => setStep(1)}
                  className="text-slate-400 font-bold text-sm mt-4 hover:text-slate-900 transition-colors"
                >
                  Create Another Tour
                </button>
              </div>
            </div>
          )}
        </main>

        {/* DESKTOP ONLY: Right Sidebar */}
        <aside className="hidden lg:flex w-80 border-l border-slate-200 flex-col bg-white overflow-y-auto p-8 gap-8 custom-scrollbar flex-shrink-0 relative z-10">
          <section className="space-y-6">
            <h3 className="text-[11px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 pb-2">
              Property Details
            </h3>
            <div className="space-y-5">
              {[
                { label: "Address", key: "address" },
                { label: "Price", key: "price" },
              ].map((f) => (
                <div key={f.key}>
                  <label className="text-[11px] text-slate-500 font-bold uppercase mb-2 block">
                    {f.label}
                  </label>
                  <input
                    type="text"
                    value={(meta as any)[f.key]}
                    onChange={(e) =>
                      setMeta({ ...meta, [f.key]: e.target.value })
                    }
                    className="w-full bg-slate-50 border border-slate-100 rounded-xl p-3 text-sm text-slate-900 outline-none focus:border-blue-500 transition-colors"
                  />
                </div>
              ))}
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: "Beds", key: "beds" },
                  { label: "Baths", key: "baths" },
                  { label: "SqFt", key: "sqft" },
                ].map((f) => (
                  <div key={f.key}>
                    <label className="text-[10px] text-slate-500 font-bold uppercase mb-2 block">
                      {f.label}
                    </label>
                    <input
                      type="text"
                      value={(meta as any)[f.key]}
                      onChange={(e) =>
                        setMeta({ ...meta, [f.key]: e.target.value })
                      }
                      className="w-full bg-slate-50 border border-slate-100 rounded-xl p-3 text-sm text-slate-900 outline-none focus:border-blue-500 transition-colors text-center"
                    />
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="space-y-4 pt-4">
            <h3 className="text-[11px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 pb-2">
              Market Compliance
            </h3>
            <div className="bg-blue-50/50 border border-blue-100 p-5 rounded-3xl space-y-5">
              <div className="flex gap-2 p-1 bg-white rounded-xl shadow-sm border border-slate-100">
                <button
                  onClick={() => setIsOwnListing(true)}
                  className={`flex-1 py-2 text-[11px] font-bold rounded-lg transition-all ${
                    isOwnListing
                      ? "bg-slate-900 text-white shadow-md"
                      : "text-slate-500 hover:text-slate-900"
                  }`}
                >
                  My Listing
                </button>
                <button
                  onClick={() => setIsOwnListing(false)}
                  className={`flex-1 py-2 text-[11px] font-bold rounded-lg transition-all ${
                    !isOwnListing
                      ? "bg-slate-900 text-white shadow-md"
                      : "text-slate-500 hover:text-slate-900"
                  }`}
                >
                  Listing Agent
                </button>
              </div>
              {!isOwnListing && (
                <div className="space-y-3 animate-in fade-in slide-in-from-top-2 duration-500">
                  <input
                    type="text"
                    placeholder="Listing Agent"
                    value={meta.agent}
                    onChange={(e) =>
                      setMeta({ ...meta, agent: e.target.value })
                    }
                    className="w-full bg-white border border-slate-200 p-3 rounded-xl text-xs text-slate-900 outline-none focus:border-blue-500 shadow-sm"
                  />
                  <input
                    type="text"
                    placeholder="Brokerage Name"
                    value={meta.brokerage}
                    onChange={(e) =>
                      setMeta({ ...meta, brokerage: e.target.value })
                    }
                    className="w-full bg-white border border-slate-200 p-3 rounded-xl text-xs text-slate-900 outline-none focus:border-blue-500 shadow-sm"
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      placeholder="MLS Source"
                      value={meta.mls_source}
                      onChange={(e) =>
                        setMeta({ ...meta, mls_source: e.target.value })
                      }
                      className="bg-white border border-slate-200 p-3 rounded-xl text-xs text-slate-900 outline-none focus:border-blue-500 shadow-sm"
                    />
                    <input
                      type="text"
                      placeholder="MLS #"
                      value={meta.mls_number}
                      onChange={(e) =>
                        setMeta({ ...meta, mls_number: e.target.value })
                      }
                      className="bg-white border border-slate-200 p-3 rounded-xl text-xs text-slate-900 outline-none focus:border-blue-500 shadow-sm"
                    />
                  </div>
                </div>
              )}
            </div>
          </section>
        </aside>
      </div>

      {/* --- OUTSIDE THE LAYOUT TRAP: MOBILE UI ELEMENTS --- */}

      {/* MOBILE LEFT DRAWER (SETTINGS) */}
      <div
        className={`fixed inset-0 z-[100] lg:hidden transition-all duration-300 ${isSettingsOpen ? "visible" : "invisible"}`}
      >
        <div
          className={`absolute inset-0 bg-slate-900/40 transition-opacity duration-300 ${isSettingsOpen ? "opacity-100" : "opacity-0"}`}
          onClick={() => setIsSettingsOpen(false)}
        />
        <aside
          className={`absolute top-0 bottom-0 left-0 w-[85vw] max-w-sm bg-white border-r border-slate-200 flex flex-col p-8 gap-8 overflow-y-auto custom-scrollbar transition-transform duration-300 ease-in-out ${isSettingsOpen ? "translate-x-0 shadow-2xl" : "-translate-x-full"}`}
        >
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-serif text-2xl font-bold text-slate-900">
              Settings
            </h2>
            <button
              onClick={() => setIsSettingsOpen(false)}
              className="p-2 bg-slate-100 rounded-full text-slate-500 hover:text-slate-900 active:scale-95 transition-all"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <SidebarSettings
            primaryColor={primaryColor}
            setPrimaryColor={setPrimaryColor}
            meta={meta}
            setMeta={setMeta}
            logoData={logoData}
            setLogoData={setLogoData}
            handleLogoUpload={(e: any) => {
              const file = e.target.files?.[0];
              if (file) {
                const reader = new FileReader();
                reader.onloadend = () => setLogoData(reader.result as string);
                reader.readAsDataURL(file);
              }
            }}
            voice={voice}
            setVoice={setVoice}
            isPreviewing={isPreviewing}
            playPreview={() => {
              const audioUrl = VOICE_PREVIEWS[voice];
              if (!audioUrl) return;
              setIsPreviewing(true);
              const audio = new Audio(audioUrl);
              audio.play().catch(() => setIsPreviewing(false));
              audio.onended = () => setIsPreviewing(false);
            }}
            format={format}
            setFormat={setFormat}
            font={font}
            setFont={setFont}
            music={music}
            setMusic={setMusic}
            language={language}
            setLanguage={setLanguage}
            user={user}
            usAuthLoading={isAuthLoading}
            showCaptions={showCaptions}
            setShowCaptions={setShowCaptions}
            enableVoice={enableVoice}
            setEnableVoice={setEnableVoice}
            enableMusic={enableMusic}
            setEnableMusic={setEnableMusic}
            saveBrandKit={saveBrandKit}
          />
          {step > 1 && (
            <button
              onClick={handleStartOver}
              className="mt-auto flex items-center justify-center gap-2 p-4 bg-red-50 border border-red-100 rounded-xl text-xs font-bold text-red-600 hover:bg-red-100 transition-all"
            >
              <RefreshCw className="w-3 h-3" /> Clear Storyboard
            </button>
          )}
        </aside>
      </div>

      {/* MOBILE RIGHT DRAWER (DETAILS) */}
      <div
        className={`fixed inset-0 z-[100] lg:hidden transition-all duration-300 ${isDetailsOpen ? "visible" : "invisible"}`}
      >
        <div
          className={`absolute inset-0 bg-slate-900/40 transition-opacity duration-300 ${isDetailsOpen ? "opacity-100" : "opacity-0"}`}
          onClick={() => setIsDetailsOpen(false)}
        />
        <aside
          className={`absolute top-0 bottom-0 right-0 w-[85vw] max-w-sm bg-white border-l border-slate-200 flex flex-col p-8 gap-8 overflow-y-auto custom-scrollbar transition-transform duration-300 ease-in-out ${isDetailsOpen ? "translate-x-0 shadow-2xl" : "translate-x-full"}`}
        >
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-serif text-2xl font-bold text-slate-900">
              Details
            </h2>
            <button
              onClick={() => setIsDetailsOpen(false)}
              className="p-2 bg-slate-100 rounded-full text-slate-500 hover:text-slate-900 active:scale-95 transition-all"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <section className="space-y-6">
            <h3 className="text-[11px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 pb-2">
              Property Details
            </h3>
            <div className="space-y-5">
              {[
                { label: "Address", key: "address" },
                { label: "Price", key: "price" },
              ].map((f) => (
                <div key={f.key}>
                  <label className="text-[11px] text-slate-500 font-bold uppercase mb-2 block">
                    {f.label}
                  </label>
                  <input
                    type="text"
                    value={(meta as any)[f.key]}
                    onChange={(e) =>
                      setMeta({ ...meta, [f.key]: e.target.value })
                    }
                    className="w-full bg-slate-50 border border-slate-100 rounded-xl p-3 text-sm text-slate-900 outline-none focus:border-blue-500 transition-colors"
                  />
                </div>
              ))}
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: "Beds", key: "beds" },
                  { label: "Baths", key: "baths" },
                  { label: "SqFt", key: "sqft" },
                ].map((f) => (
                  <div key={f.key}>
                    <label className="text-[10px] text-slate-500 font-bold uppercase mb-2 block">
                      {f.label}
                    </label>
                    <input
                      type="text"
                      value={(meta as any)[f.key]}
                      onChange={(e) =>
                        setMeta({ ...meta, [f.key]: e.target.value })
                      }
                      className="w-full bg-slate-50 border border-slate-100 rounded-xl p-3 text-sm text-slate-900 outline-none focus:border-blue-500 transition-colors text-center"
                    />
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="space-y-4 pt-4">
            <h3 className="text-[11px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 pb-2">
              Market Compliance
            </h3>
            <div className="bg-blue-50/50 border border-blue-100 p-5 rounded-3xl space-y-5">
              <div className="flex gap-2 p-1 bg-white rounded-xl shadow-sm border border-slate-100">
                <button
                  onClick={() => setIsOwnListing(true)}
                  className={`flex-1 py-2 text-[11px] font-bold rounded-lg transition-all ${
                    isOwnListing
                      ? "bg-slate-900 text-white shadow-md"
                      : "text-slate-500 hover:text-slate-900"
                  }`}
                >
                  My Listing
                </button>
                <button
                  onClick={() => setIsOwnListing(false)}
                  className={`flex-1 py-2 text-[11px] font-bold rounded-lg transition-all ${
                    !isOwnListing
                      ? "bg-slate-900 text-white shadow-md"
                      : "text-slate-500 hover:text-slate-900"
                  }`}
                >
                  Listing Agent
                </button>
              </div>
              {!isOwnListing && (
                <div className="space-y-3 animate-in fade-in slide-in-from-top-2 duration-500">
                  <input
                    type="text"
                    placeholder="Listing Agent"
                    value={meta.agent}
                    onChange={(e) =>
                      setMeta({ ...meta, agent: e.target.value })
                    }
                    className="w-full bg-white border border-slate-200 p-3 rounded-xl text-xs text-slate-900 outline-none focus:border-blue-500 shadow-sm"
                  />
                  <input
                    type="text"
                    placeholder="Brokerage Name"
                    value={meta.brokerage}
                    onChange={(e) =>
                      setMeta({ ...meta, brokerage: e.target.value })
                    }
                    className="w-full bg-white border border-slate-200 p-3 rounded-xl text-xs text-slate-900 outline-none focus:border-blue-500 shadow-sm"
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      placeholder="MLS Source"
                      value={meta.mls_source}
                      onChange={(e) =>
                        setMeta({ ...meta, mls_source: e.target.value })
                      }
                      className="bg-white border border-slate-200 p-3 rounded-xl text-xs text-slate-900 outline-none focus:border-blue-500 shadow-sm"
                    />
                    <input
                      type="text"
                      placeholder="MLS #"
                      value={meta.mls_number}
                      onChange={(e) =>
                        setMeta({ ...meta, mls_number: e.target.value })
                      }
                      className="bg-white border border-slate-200 p-3 rounded-xl text-xs text-slate-900 outline-none focus:border-blue-500 shadow-sm"
                    />
                  </div>
                </div>
              )}
            </div>
          </section>
        </aside>
      </div>

      {/* MOBILE BOTTOM NAVIGATION DOCK */}
      {step === 2 && !isRendering && (
        <div className="lg:hidden fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur-xl border-t border-slate-200 p-4 z-[90] pb-safe shadow-[0_-10px_40px_rgba(0,0,0,0.1)]">
          <div className="flex items-center justify-between max-w-md mx-auto px-2">
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="flex flex-col items-center gap-1.5 p-2 text-slate-500 hover:text-blue-600 transition-colors"
            >
              <Settings className="w-6 h-6" />
              <span className="text-[10px] font-bold">Design</span>
            </button>

            <div className="relative -top-6">
              <button
                onClick={handleRenderVideo}
                disabled={!isCompliant}
                className="bg-slate-900 text-white rounded-full p-5 shadow-2xl shadow-slate-900/40 disabled:opacity-40 active:scale-95 transition-all"
              >
                <Film className="w-6 h-6 text-blue-400" />
              </button>
            </div>

            <button
              onClick={() => setIsDetailsOpen(true)}
              className="flex flex-col items-center gap-1.5 p-2 text-slate-500 hover:text-blue-600 transition-colors relative"
            >
              <div className="relative">
                <Globe className="w-6 h-6" />
                {!isCompliant && (
                  <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full border-2 border-white animate-pulse" />
                )}
              </div>
              <span className="text-[10px] font-bold">Details</span>
            </button>
          </div>
        </div>
      )}

      {/* --- CLEAR CONFIRMATION MODAL --- */}
      {showClearConfirmModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-md z-[200] flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 p-8 sm:p-10 rounded-[2.5rem] max-w-sm w-full text-center shadow-2xl relative animate-in zoom-in-95 duration-200">
            <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-6">
              <Trash2 className="w-8 h-8 text-red-500" />
            </div>
            <h2 className="font-serif text-3xl font-bold text-slate-900 mb-2 tracking-tight">
              Start Over?
            </h2>
            <p className="text-slate-500 text-sm mb-8 leading-relaxed">
              This will permanently clear your current storyboard, captions, and
              property details. This action cannot be undone.
            </p>
            <div className="flex flex-col gap-3">
              <button
                onClick={executeStartOver}
                className="w-full bg-red-500 hover:bg-red-600 py-4 rounded-xl font-bold text-white transition-all shadow-lg shadow-red-500/20 active:scale-95 flex items-center justify-center gap-2"
              >
                <RefreshCw className="w-4 h-4" /> Yes, Clear Storyboard
              </button>
              <button
                onClick={() => setShowClearConfirmModal(false)}
                className="w-full bg-slate-50 hover:bg-slate-100 text-slate-600 py-4 rounded-xl font-bold transition-all"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --- TOP-UP MODAL --- */}
      {showTopUpModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-md z-[200] flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 p-12 rounded-[3.5rem] max-w-sm w-full text-center shadow-2xl">
            <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-8">
              <AlertCircle className="w-8 h-8 text-blue-600" />
            </div>
            <h2 className="font-serif text-3xl font-bold text-slate-900 mb-2">
              Replenish
            </h2>
            <p className="text-slate-500 text-sm mb-8 leading-relaxed">
              Your storyboard is saved. Add render credits to create your video.
            </p>
            <button
              onClick={handleBuyCredits}
              className="w-full bg-blue-600 hover:bg-blue-700 py-5 rounded-2xl font-bold text-white transition-all shadow-xl active:scale-95"
            >
              5 HD Credits — $25
            </button>
            <button
              onClick={() => setShowTopUpModal(false)}
              className="mt-4 text-slate-400 text-xs font-bold hover:text-slate-600 transition-colors"
            >
              Back to Editor
            </button>
          </div>
        </div>
      )}
    </div>
  );
}