'use client';

import { useState, useEffect } from 'react';
import { supabase } from '../../lib/supabase';
import { Film, ArrowLeft, Loader2, MapPin, Calendar, Download, Share2, Trash2, Clock } from 'lucide-react';
import Link from 'next/link';

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

  useEffect(() => {
    fetchMyVideos();
  }, []);

  const fetchMyVideos = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      
      if (!session?.user) {
        window.location.href = '/'; 
        return;
      }
      
      setUserEmail(session.user.email || null);

      const { data, error } = await supabase
        .from('user_videos')
        .select('*')
        .eq('user_id', session.user.id)
        .order('created_at', { ascending: false });

      if (error) throw error;
      setVideos(data || []);
      
    } catch (error) {
      console.error('Error fetching videos:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownload = (url: string, address: string) => {
    const a = document.createElement('a');
    a.href = `${url}?download=`; 
    a.target = '_blank';
    a.download = `${address.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.mp4`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const handleShare = async (url: string) => {
    const fbUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`;
    window.open(fbUrl, '_blank', 'width=600,height=500,scrollbars=yes');
  };

  const handleDelete = async (videoId: string, videoUrl: string) => {
    if (!window.confirm("Are you sure you want to delete this video? This cannot be undone.")) return;

    try {
      const fileName = videoUrl.split('/').pop()?.split('?')[0];

      if (fileName) {
        const { error: storageError } = await supabase.storage
          .from('listings')
          .remove([fileName]);
          
        if (storageError) console.error("Could not delete from storage:", storageError);
      }

      const { error: dbError } = await supabase
        .from('user_videos')
        .delete()
        .eq('id', videoId);

      if (dbError) throw dbError;

      setVideos(videos.filter(v => v.id !== videoId));

    } catch (error) {
      console.error('Error deleting video:', error);
      alert("Failed to delete video. Please try again.");
    }
  };

  const formatDate = (dateString: string) => {
    const options: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric', year: 'numeric' };
    return new Date(dateString).toLocaleDateString('en-US', options);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-neutral-200 font-sans p-6 md:p-10 selection:bg-indigo-500/30">
      <div className="max-w-7xl mx-auto">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 pb-6 border-b border-neutral-800">
          <div>
            <Link href="/" className="inline-flex items-center gap-2 text-sm text-neutral-400 hover:text-white transition-colors mb-4">
              <ArrowLeft className="w-4 h-4" /> Back to Studio
            </Link>
            <h1 className="text-3xl font-bold text-white flex items-center gap-3">
              <Film className="w-7 h-7 text-indigo-400" /> My Video Library
            </h1>
            <p className="text-neutral-500 mt-1">Logged in as {userEmail}</p>
          </div>
          <Link href="/" className="bg-white hover:bg-neutral-200 text-black font-semibold py-2.5 px-6 rounded-xl transition-all shadow-lg w-fit">
            + New Video
          </Link>
        </div>

        {/* 7-DAY WARNING BANNER */}
        {!isLoading && videos.length > 0 && (
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 mb-8 flex items-start gap-3 text-amber-200/90 text-sm">
            <Clock className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
            <p><strong>Storage Notice:</strong> To ensure fast performance, rendered videos are automatically deleted from our servers <strong>7 days</strong> after creation. Please download your files if you wish to keep them permanently.</p>
          </div>
        )}

        {/* Loading State */}
        {isLoading ? (
          <div className="flex flex-col items-center justify-center min-h-[40vh]">
            <Loader2 className="w-10 h-10 text-indigo-500 animate-spin mb-4" />
            <p className="text-neutral-400">Loading your masterpiece collection...</p>
          </div>
        ) : videos.length === 0 ? (
          
          /* Empty State */
          <div className="bg-neutral-900/40 border border-neutral-800 rounded-2xl p-12 text-center max-w-2xl mx-auto mt-10">
            <div className="bg-neutral-950 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 ring-1 ring-white/5">
              <Film className="w-10 h-10 text-neutral-600" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">No videos yet</h2>
            <p className="text-neutral-400 mb-8">You haven't rendered any cinematic listing videos. Head back to the studio to create your first one!</p>
            <Link href="/" className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 px-8 rounded-xl transition-all shadow-lg shadow-indigo-500/20 inline-flex items-center gap-2">
              Go to Studio
            </Link>
          </div>
          
        ) : (
          
          /* COMPACT VIDEO GRID */
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {videos.map((video) => (
              <div key={video.id} className="bg-neutral-900/50 border border-neutral-800 rounded-xl overflow-hidden hover:border-neutral-700 transition-all group flex flex-col relative">
                
                {/* FLOATING DELETE BUTTON */}
                <button 
                  onClick={() => handleDelete(video.id, video.video_url)}
                  className="absolute top-2 right-2 z-10 bg-black/60 hover:bg-red-500/90 text-white p-1.5 rounded-md backdrop-blur-sm transition-colors opacity-0 group-hover:opacity-100"
                  title="Delete Video"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>

                {/* Video Player */}
                <div className="aspect-video bg-black relative">
                  <video 
                    src={video.video_url} 
                    controls 
                    className="w-full h-full object-contain"
                    preload="metadata"
                  />
                </div>
                
                {/* COMPACT Video Details */}
                <div className="p-3.5 flex flex-col flex-1">
                  <h3 className="text-sm font-bold text-white mb-1.5 flex items-start gap-1.5 line-clamp-2 leading-snug">
                    <MapPin className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-[2px]" /> 
                    {video.property_address}
                  </h3>
                  
                  <div className="flex items-center gap-1.5 text-[11px] font-medium text-neutral-500 mb-3">
                    <Calendar className="w-3 h-3" />
                    {formatDate(video.created_at)}
                  </div>
                  
                  {/* COMPACT Actions */}
                  <div className="flex gap-2 mt-auto pt-3 border-t border-neutral-800/60">
                    <button 
                      onClick={() => handleDownload(video.video_url, video.property_address)}
                      className="flex-1 bg-neutral-800 hover:bg-neutral-700 text-white text-xs font-semibold py-1.5 rounded-md flex items-center justify-center gap-1.5 transition-colors"
                    >
                      <Download className="w-3.5 h-3.5" /> Download
                    </button>
                    <button 
                      onClick={() => handleShare(video.video_url)}
                      className="flex-1 bg-[#1877F2]/10 hover:bg-[#1877F2]/20 text-[#1877F2] text-xs font-semibold py-1.5 rounded-md flex items-center justify-center gap-1.5 transition-colors"
                    >
                      <Share2 className="w-3.5 h-3.5" /> Share
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}