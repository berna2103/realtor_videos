"use client";

import { useState, useEffect } from "react";
import { supabase } from "../../lib/supabase";
import {
  Film,
  ArrowLeft,
  Loader2,
  MapPin,
  Calendar,
  Download,
  Share2,
  Trash2,
  Clock,
  Plus,
  LayoutDashboard,
} from "lucide-react";
import Link from "next/link";

interface UserVideo {
  id: string;
  video_url: string;
  property_address: string;
  created_at: string;
}

export default function MyVideosDashboard() {
  const [videos, setVideos] = useState<UserVideo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  // UI States for Custom Modal & Loading
  const [isDeletingId, setIsDeletingId] = useState<string | null>(null);
  const [videoToDelete, setVideoToDelete] = useState<{
    id: string;
    url: string;
  } | null>(null);

  useEffect(() => {
    let mounted = true;

    const getInitialSession = async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (session?.user && mounted) {
        setUserEmail(session.user.email || null);
        fetchMyVideos(session.user.id);
      }

      const {
        data: { subscription },
      } = supabase.auth.onAuthStateChange((_event, session) => {
        if (session?.user && mounted) {
          setUserEmail(session.user.email || null);
          fetchMyVideos(session.user.id);
        } else if (_event === "SIGNED_OUT") {
          window.location.href = "/";
        }
      });

      return () => subscription.unsubscribe();
    };

    getInitialSession();
    return () => {
      mounted = false;
    };
  }, []);

  const fetchMyVideos = async (userId: string) => {
    setIsLoading(true);
    try {
      const { data, error } = await supabase
        .from("user_videos")
        .select("*")
        .eq("user_id", userId)
        .order("created_at", { ascending: false });

      if (error) throw error;
      setVideos(data || []);
    } catch (error) {
      console.error("Fetch error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  // REFINED DELETE LOGIC (Fixes Ghost Clicks)
  const confirmDelete = async (e: React.MouseEvent) => {
    e.preventDefault(); // Stop click from hitting elements underneath

    if (!videoToDelete) return;
    const { id: videoId, url: videoUrl } = videoToDelete;

    setIsDeletingId(videoId); // Lock the UI and show loaders

    try {
      const fileName = videoUrl.split("/").pop()?.split("?")[0];
      if (fileName) {
        await supabase.storage.from("listings").remove([fileName]);
      }

      const { error } = await supabase
        .from("user_videos")
        .delete()
        .eq("id", videoId);
      if (error) throw error;

      // Update UI only after safe deletion from database
      setVideos(videos.filter((v) => v.id !== videoId));
    } catch (error) {
      console.error("Delete failed:", error);
    } finally {
      setIsDeletingId(null);
      setVideoToDelete(null); // Safe to close the modal now!
    }
  };

  const handleDownload = (url: string, address: string) => {
    const a = document.createElement("a");
    a.href = `${url}?download=`;
    a.target = "_blank";
    a.download = `${address.replace(/[^a-z0-9]/gi, "_").toLowerCase()}.mp4`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const handleShare = async (url: string) => {
    const fbUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`;
    window.open(fbUrl, "_blank", "width=600,height=500,scrollbars=yes");
  };

  const formatDate = (dateString: string) => {
    const options: Intl.DateTimeFormatOptions = {
      month: "short",
      day: "numeric",
      year: "numeric",
    };
    return new Date(dateString).toLocaleDateString("en-US", options);
  };

  return (
    <div className="min-h-screen bg-[#F9FAFB] text-slate-900 font-sans p-6 md:p-12 selection:bg-blue-100">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12 pb-8 border-b border-slate-200">
          <div>
            <Link
              href="/"
              className="inline-flex items-center gap-2 text-sm font-bold text-blue-600 hover:text-blue-700 transition-colors mb-6 group"
            >
              <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />{" "}
              Back to Studio
            </Link>
            <h1 className="font-serif text-5xl font-bold text-slate-900 tracking-tight">
              Video Library
            </h1>
            <p className="text-slate-500 mt-2 font-medium">
              Managing assets for{" "}
              <span className="text-slate-900">{userEmail}</span>
            </p>
          </div>
          <Link
            href="/"
            className="bg-slate-900 hover:bg-black text-white font-bold py-4 px-8 rounded-2xl transition-all shadow-xl shadow-slate-200 flex items-center gap-2 active:scale-95"
          >
            <Plus className="w-5 h-5" /> Create New Tour
          </Link>
        </div>

        {/* Storage Warning */}
        {!isLoading && videos.length > 0 && (
          <div className="bg-amber-50 border border-amber-100 rounded-2xl p-5 mb-10 flex items-start gap-4 text-amber-800 text-sm shadow-sm shadow-amber-100/50">
            <div className="bg-white p-2 rounded-lg shadow-sm border border-amber-100">
              <Clock className="w-5 h-5 text-amber-600 shrink-0" />
            </div>
            <div className="flex-1">
              <p className="font-bold mb-0.5">Automated Storage Cleanup</p>
              <p className="text-amber-700/80">
                Videos are hosted for 7 days. Please download your finalized
                MP4s for permanent access.
              </p>
            </div>
          </div>
        )}

        {/* Main Content */}
        {isLoading ? (
          <div className="flex flex-col items-center justify-center min-h-[40vh]">
            <Loader2 className="w-12 h-12 text-blue-600 animate-spin mb-4" />
            <p className="text-slate-500 font-medium">
              Fetching your cinematic collection...
            </p>
          </div>
        ) : videos.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-[3rem] p-16 text-center max-w-2xl mx-auto mt-10 shadow-2xl shadow-slate-200/50">
            <div className="bg-slate-50 w-24 h-24 rounded-full flex items-center justify-center mx-auto mb-8 ring-1 ring-slate-100 shadow-inner">
              <Film className="w-10 h-10 text-slate-300" />
            </div>
            <h2 className="font-serif text-3xl font-bold text-slate-900 mb-3">
              Your library is empty
            </h2>
            <p className="text-slate-500 mb-10 text-lg leading-relaxed">
              Head back to the studio and turn a listing into a cinematic
              masterpiece.
            </p>
            <Link
              href="/"
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 px-10 rounded-2xl transition-all shadow-lg shadow-blue-100"
            >
              Start Building
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-8">
            {videos.map((video) => (
              <div
                key={video.id}
                className="bg-white border border-slate-200 rounded-[2rem] overflow-hidden hover:shadow-2xl hover:border-blue-200 transition-all duration-500 group flex flex-col relative shadow-xl shadow-slate-200/40"
              >
                {/* Fixed Custom Delete Trigger */}
                <button
                  onClick={() =>
                    setVideoToDelete({ id: video.id, url: video.video_url })
                  }
                  className="absolute top-4 right-4 z-20 bg-white/90 hover:bg-red-50 text-red-500 p-2.5 rounded-xl backdrop-blur-md transition-all shadow-lg opacity-0 group-hover:opacity-100 border border-red-50"
                >
                  {isDeletingId === video.id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                </button>

                <div className="aspect-[9/16] bg-slate-900 relative overflow-hidden">
                  <video
                    src={video.video_url}
                    controls
                    className="w-full h-full object-cover opacity-90 group-hover:opacity-100 transition-opacity"
                    preload="metadata"
                  />
                  <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/40 to-transparent pointer-events-none" />
                </div>

                <div className="p-6 flex flex-col flex-1">
                  <div className="flex items-start gap-2 mb-3">
                    <MapPin className="w-4 h-4 text-blue-600 shrink-0 mt-1" />
                    <h3 className="text-base font-bold text-slate-900 line-clamp-2 leading-tight tracking-tight">
                      {video.property_address}
                    </h3>
                  </div>
                  <div className="flex items-center gap-2 text-[12px] font-bold text-slate-400 uppercase tracking-widest mb-6">
                    <Calendar className="w-3.5 h-3.5" />
                    {formatDate(video.created_at)}
                  </div>
                  <div className="flex gap-3 mt-auto pt-4 border-t border-slate-100">
                    <button
                      onClick={() =>
                        handleDownload(video.video_url, video.property_address)
                      }
                      className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-900 text-xs font-black uppercase tracking-widest py-3 rounded-xl flex items-center justify-center gap-2 transition-all active:scale-95"
                    >
                      <Download className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleShare(video.video_url)}
                      className="flex-1 bg-blue-50 hover:bg-blue-100 text-blue-600 text-xs font-black uppercase tracking-widest py-3 rounded-xl flex items-center justify-center gap-2 transition-all active:scale-95"
                    >
                      <Share2 className="w-3.5 h-3.5" />
                    </button>
                    {/* New Dashboard Button */}
                    <a
                      href="/dashboard"
                      className="flex-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 text-xs font-black uppercase tracking-widest py-3 rounded-xl flex items-center justify-center gap-2 transition-all active:scale-95"
                    >
                      <LayoutDashboard className="w-3.5 h-3.5" />
                    </a>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* CUSTOM LUXURY DELETE MODAL */}
        {videoToDelete && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
            <div className="bg-white border border-slate-200 rounded-[2.5rem] p-10 max-w-sm w-full shadow-2xl animate-in zoom-in-95 duration-200">
              <div className="w-16 h-16 bg-red-50 rounded-2xl flex items-center justify-center mx-auto mb-6">
                <Trash2 className="w-8 h-8 text-red-500" />
              </div>
              <h3 className="font-serif text-2xl font-bold text-slate-900 text-center mb-2 tracking-tight">
                Archive Tour?
              </h3>
              <p className="text-slate-500 text-center text-sm mb-8 leading-relaxed font-medium">
                This will permanently remove the cinematic tour from your
                library. This action cannot be undone.
              </p>
              <div className="flex flex-col gap-3">
                <button
                  onClick={confirmDelete}
                  disabled={isDeletingId === videoToDelete.id}
                  className="w-full bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold py-4 rounded-2xl transition-all active:scale-95 shadow-lg shadow-red-100 flex items-center justify-center gap-2"
                >
                  {isDeletingId === videoToDelete.id ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" /> Deleting...
                    </>
                  ) : (
                    "Confirm Delete"
                  )}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
