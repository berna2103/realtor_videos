"use client";

import { useState, useEffect } from "react";
import { supabase } from "../../lib/supabase";
import { useAuth } from "../../context/AuthContext";
import {
  Film,
  ArrowLeft,
  Loader2,
  Download,
  Share2,
  Trash2,
  Plus,
  LogOut,
} from "lucide-react";
import Link from "next/link";

interface UserVideo {
  id: string;
  video_url: string;
  property_address: string;
  created_at: string;
}

export default function MyVideosDashboard() {
  const { user, email, isLoading: authLoading, signOut } = useAuth();
  const [videos, setVideos] = useState<UserVideo[]>([]);
  const [isFetchingVideos, setIsFetchingVideos] = useState(true);
  const [isMounted, setIsMounted] = useState(false);
  const [isDeletingId, setIsDeletingId] = useState<string | null>(null);
  const [videoToDelete, setVideoToDelete] = useState<{
    id: string;
    url: string;
  } | null>(null);

  // 1. Prevent Hydration Mismatch
  useEffect(() => {
    setIsMounted(true);
  }, []);

  // 2. Fetch videos once auth is ready
  useEffect(() => {
    if (isMounted && user) {
      fetchMyVideos(user.id);
    } else if (isMounted && !authLoading && !user) {
      setIsFetchingVideos(false);
    }
  }, [user, authLoading, isMounted]);

  const fetchMyVideos = async (userId: string) => {
    setIsFetchingVideos(true);
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
      setIsFetchingVideos(false);
    }
  };

  const confirmDelete = async () => {
    if (!videoToDelete) return;
    setIsDeletingId(videoToDelete.id);
    try {
      const fileName = videoToDelete.url.split("/").pop()?.split("?")[0];
      if (fileName) await supabase.storage.from("listings").remove([fileName]);
      await supabase.from("user_videos").delete().eq("id", videoToDelete.id);
      setVideos(videos.filter((v) => v.id !== videoToDelete.id));
    } catch (error) {
      console.error("Delete failed:", error);
    } finally {
      setIsDeletingId(null);
      setVideoToDelete(null);
    }
  };
const handleDownload = async (url: string, address: string) => {
    try {
      // Fetch the file from Supabase
      const response = await fetch(url);
      const blob = await response.blob();
      
      // Create a local URL for the downloaded data
      const blobUrl = window.URL.createObjectURL(blob);
      
      // Create a temporary link and trigger the download
      const link = document.createElement("a");
      link.href = blobUrl;
      
      // Format the address into a safe filename (e.g., "123-Main-St.mp4")
      const safeFileName = address.replace(/[^a-z0-9]/gi, '-').toLowerCase();
      link.download = `${safeFileName}.mp4`;
      
      document.body.appendChild(link);
      link.click();
      
      // Clean up
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
    } catch (error) {
      console.error("Download failed:", error);
      alert("Failed to download the video. Please try again.");
    }
  };
  // Show loader while checking auth or mounting
  if (!isMounted || authLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#F9FAFB]">
        <Loader2 className="w-12 h-12 text-blue-600 animate-spin mb-4" />
        <p className="text-slate-500 font-medium">Loading your library...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F9FAFB] p-6 md:p-12">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12 pb-8 border-b border-slate-200">
          <div>
            <Link
              href="/create"
              className="inline-flex items-center gap-2 text-sm font-bold text-blue-600 mb-6 group"
            >
              <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />{" "}
              Back to Studio
            </Link>
            <h1 className="text-5xl font-bold text-slate-900 tracking-tight">
              Video Library
            </h1>
            <p className="text-slate-500 mt-2 font-medium">
              Managing assets for{" "}
              <span className="text-slate-900">{email}</span>
            </p>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={async () => {
                await signOut();
                window.location.href = "/"; // Instantly kicks them back to landing page
              }}
              title="Sign Out"
              className="p-3 rounded-full text-slate-400 hover:text-red-500 hover:bg-red-50 transition-all cursor-pointer flex items-center justify-center active:scale-95"
            >
              <LogOut className="w-6 h-6" />
            </button>
            <Link
              href="/create"
              className="bg-slate-900 text-white font-bold py-4 px-8 rounded-2xl flex items-center gap-2"
            >
              <Plus className="w-5 h-5" /> Create New Tour
            </Link>
          </div>
        </div>

        {isFetchingVideos ? (
          <div className="flex flex-col items-center justify-center min-h-[40vh]">
            <Loader2 className="w-12 h-12 text-blue-600 animate-spin mb-4" />
          </div>
        ) : videos.length === 0 ? (
          <div className="bg-white border rounded-[3rem] p-16 text-center max-w-2xl mx-auto mt-10 shadow-2xl">
            <Film className="w-10 h-10 text-slate-300 mx-auto mb-8" />
            <h2 className="text-3xl font-bold text-slate-900 mb-3">
              Your library is empty
            </h2>
            <Link
              href="/"
              className="bg-blue-600 text-white font-bold py-4 px-10 rounded-2xl inline-block mt-6"
            >
              Start Building
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-8">
            {videos.map((video) => (
              <div
                key={video.id}
                className="bg-white border border-slate-200 rounded-[2rem] overflow-hidden group relative shadow-xl"
              >
                <div className="aspect-[9/16] bg-slate-900">
                  <video
                    src={video.video_url}
                    controls
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="p-6 flex flex-col flex-grow">
  <h3 className="text-base font-bold text-slate-900 line-clamp-2 mb-4">
    {video.property_address}
  </h3>
  
  <div className="mt-auto pt-4 border-t border-slate-100 flex items-center justify-between">
    <div className="flex gap-4">
      <button
        onClick={() => {
          navigator.clipboard.writeText(video.video_url);
          alert("Video link copied to clipboard!");
        }}
        className="text-slate-500 hover:text-blue-600 flex items-center gap-1.5 text-sm font-semibold transition-colors"
        title="Copy Link"
      >
        <Share2 className="w-4 h-4" /> Share
      </button>
      
      <button
        onClick={() => handleDownload(video.video_url, video.property_address)}
        className="text-slate-500 hover:text-blue-600 flex items-center gap-1.5 text-sm font-semibold transition-colors"
        title="Download Video"
      >
        <Download className="w-4 h-4" /> Save
      </button>
    </div>

    <button
      onClick={() =>
        setVideoToDelete({ id: video.id, url: video.video_url })
      }
      className="text-red-500 hover:text-red-700 text-sm font-bold flex items-center gap-1.5 transition-colors"
      title="Delete Video"
    >
      <Trash2 className="w-4 h-4" /> Delete
    </button>
  </div>
</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete Modal */}
      {videoToDelete && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="bg-white p-10 rounded-[2.5rem] max-w-sm w-full shadow-2xl">
            <h3 className="text-2xl font-bold text-center mb-4">
              Delete Video?
            </h3>
            <div className="flex flex-col gap-3">
              <button
                onClick={confirmDelete}
                className="bg-red-600 text-white py-4 rounded-xl font-bold"
              >
                {isDeletingId ? "Deleting..." : "Confirm Delete"}
              </button>
              <button
                onClick={() => setVideoToDelete(null)}
                className="bg-slate-100 py-4 rounded-xl font-bold"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}