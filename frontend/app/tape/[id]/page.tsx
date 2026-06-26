'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Download, Share2, Flag, Play, Pause, ExternalLink } from 'lucide-react';
import WaveformPlayer from '../../components/WaveformPlayer';
import RemixTree from '../../components/RemixTree';
import C2PABadge from '../../components/C2PABadge';
import StreakBadge from '../../components/StreakBadge';
import { useAuth } from '@clerk/nextjs';

export default function TapeDetailPage() {
  const params = useParams();
  const tapeId = params.id as string;

  const [tape, setTape] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);
  const [showTikTokModal, setShowTikTokModal] = useState(false);

  const [tiktokCaption, setTiktokCaption] = useState('');
  const [useOriginalAudio, setUseOriginalAudio] = useState(true);
  const [postingToTikTok, setPostingToTikTok] = useState(false);
  const { getToken } = useAuth();

  useEffect(() => {
    fetchTape();
  }, [tapeId]);

  const fetchTape = async () => {
    try {
      const token = await getToken();
      const response = await fetch(`/api/tapes/${tapeId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const data = await response.json();
      setTape(data);
    } catch (error) {
      console.error('Failed to load tape:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!tape) return;
    
    try {
      const token = await getToken();
      const response = await fetch(`/api/tapes/${tapeId}/download`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${tape.id}.mp3`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Download failed:', error);
    }
  };

  const handlePostToTikTok = async () => {
    if (postingToTikTok) return;
    setPostingToTikTok(true);

    try {
      const token = await getToken();
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBaseUrl}/api/v1/tiktok/upload`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          generation_id: tapeId,
          caption: tiktokCaption,
          use_original_audio: useOriginalAudio,
        }),
      });

      if (response.ok) {
        // Log TikTok share metric
        try {
          await fetch(`${apiBaseUrl}/api/v2/metrics`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(token && { Authorization: `Bearer ${token}` }),
            },
            body: JSON.stringify({
              generation_id: tapeId,
              action: 'tiktok_share',
            }),
          });
        } catch (err) {
          console.warn('Failed to log TikTok share metric:', err);
        }

        alert('Successfully posted to TikTok! Processing may take a few minutes.');
        setShowTikTokModal(false);
        setTiktokCaption('');
      } else {
        const errorData = await response.json();
        if (response.status === 400 && errorData.detail?.includes('not connected')) {
          if (confirm('Your TikTok account is not connected. Would you like to connect it now?')) {
            window.location.href = `${apiBaseUrl}/api/v1/tiktok/auth`;
          }
        } else {
          alert(errorData.detail || 'Failed to post to TikTok');
        }
      }
    } catch (error) {
      console.error('TikTok post error:', error);
      alert('Failed to post to TikTok');
    } finally {
      setPostingToTikTok(false);
    }
  };

  const handleShare = async () => {
    const shareUrl = `${window.location.origin}/tape/${tapeId}`;
    
    if (navigator.share) {
      try {
        await navigator.share({
          title: `Check out this tape: ${tape.prompt}`,
          url: shareUrl,
        });
      } catch (error) {
        // User cancelled
      }
    } else {
      await navigator.clipboard.writeText(shareUrl);
      alert('Link copied to clipboard!');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#7c3aed]"></div>
      </div>
    );
  }

  if (!tape) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-2">Tape not found</h2>
          <Link href="/dashboard" className="text-[#7c3aed] hover:underline">
            Back to Explore
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a]">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#1a1a1a] border-b border-gray-800">
        <div className="container mx-auto px-4 py-4">
          <Link href="/dashboard" className="flex items-center space-x-2 text-gray-400 hover:text-white">
            <ArrowLeft className="w-5 h-5" />
            <span>Back to Explore</span>
          </Link>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        <div className="grid lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Waveform Player */}
            <div className="bg-[#1a1a1a] rounded-lg p-6">
              <WaveformPlayer
                audioUrl={tape.audio_url}
                generationId={tape.id}
                waveformData={tape.waveform_data}
                onPlayStateChange={setIsPlaying}
                height={120}
              />
            </div>

            {/* Prompt & Info */}
            <div className="bg-[#1a1a1a] rounded-lg p-6">
              <h1 className="text-2xl font-bold text-white mb-4">{tape.prompt}</h1>
              
              <div className="flex flex-wrap gap-4 text-sm">
                <div className="flex items-center space-x-2">
                  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                  </svg>
                  <span className="text-gray-400">{tape.remix_count} remixes</span>
                </div>
                
                <div className="flex items-center space-x-2">
                  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="text-gray-400">€{tape.total_earnings.toFixed(2)} earned</span>
                </div>

                <div className="flex items-center space-x-2">
                  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                  <span className="text-gray-400">{tape.plays_count} plays</span>
                </div>

                {tape.has_c2pa && <C2PABadge generationId={tapeId} />}
              </div>
            </div>

            {/* Actions */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Link
                href={`/create?parent=${tapeId}`}
                className="py-3 bg-[#7c3aed] text-white rounded-lg font-medium hover:bg-[#6d28d9] transition-colors text-center"
              >
                Remix This
              </Link>
              
              <button
                onClick={handleDownload}
                className="py-3 bg-[#1a1a1a] text-white rounded-lg font-medium hover:bg-[#2a2a2a] transition-colors flex items-center justify-center space-x-2"
              >
                <Download className="w-4 h-4" />
                <span>Download</span>
              </button>
              
              <button
                onClick={() => setShowTikTokModal(true)}
                className="py-3 bg-[#1a1a1a] text-white rounded-lg font-medium hover:bg-[#2a2a2a] transition-colors flex items-center justify-center space-x-2"
              >
                <ExternalLink className="w-4 h-4" />
                <span>TikTok</span>
              </button>
              
              <button
                onClick={handleShare}
                className="py-3 bg-[#1a1a1a] text-white rounded-lg font-medium hover:bg-[#2a2a2a] transition-colors flex items-center justify-center space-x-2"
              >
                <Share2 className="w-4 h-4" />
                <span>Share</span>
              </button>
            </div>

            {/* Remix Tree */}
            <div className="bg-[#1a1a1a] rounded-lg p-6">
              <h3 className="text-xl font-bold text-white mb-6">Remix Tree</h3>
              <RemixTree tapeId={tapeId} />
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Creator Info */}
            <div className="bg-[#1a1a1a] rounded-lg p-6">
              <h3 className="text-white font-bold mb-4">Creator</h3>
              <Link href={`/profile/${tape.creator.id}`} className="flex items-center space-x-3 mb-4">
                <div className="w-16 h-16 rounded-full bg-[#7c3aed] flex items-center justify-center text-white font-bold text-xl">
                  {tape.creator.avatar_url ? (
                    <img
                      src={tape.creator.avatar_url}
                      alt={tape.creator.username}
                      className="w-full h-full rounded-full object-cover"
                    />
                  ) : (
                    tape.creator.username.charAt(0).toUpperCase()
                  )}
                </div>
                <div>
                  <div className="text-white font-medium">{tape.creator.username}</div>
                  <div className="text-gray-400 text-sm">{tape.creator.tapes_count} tapes</div>
                </div>
              </Link>
              
              {tape.creator.streak_days > 0 && (
                <div className="mb-4">
                  <StreakBadge days={tape.creator.streak_days} size="md" />
                </div>
              )}

              <button className="w-full py-2 bg-[#7c3aed] text-white rounded-lg font-medium hover:bg-[#6d28d9] transition-colors">
                Follow
              </button>
            </div>

            {/* Stats */}
            <div className="bg-[#1a1a1a] rounded-lg p-6">
              <h3 className="text-white font-bold mb-4">Stats</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-400">Created</span>
                  <span className="text-white">{new Date(tape.created_at).toLocaleDateString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Layer Type</span>
                  <span className="text-white capitalize">{tape.layer_type}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Duration</span>
                  <span className="text-white">{tape.duration}s</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Likes</span>
                  <span className="text-white">{tape.likes_count}</span>
                </div>
              </div>
            </div>

            {/* Report */}
            <button
              onClick={() => setShowReportModal(true)}
              className="w-full py-2 bg-[#1a1a1a] text-red-400 rounded-lg font-medium hover:bg-[#2a2a2a] transition-colors flex items-center justify-center space-x-2"
            >
              <Flag className="w-4 h-4" />
              <span>Report Content</span>
            </button>
          </div>
        </div>
      </div>

      {/* Report Modal */}
      {showReportModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#1a1a1a] rounded-lg max-w-md w-full p-6">
            <h3 className="text-xl font-bold text-white mb-4">Report Content</h3>
            <p className="text-gray-400 mb-4">Why are you reporting this tape?</p>
            
            <div className="space-y-2 mb-6">
              {['Copyright infringement', 'Inappropriate content', 'Spam', 'Other'].map((reason) => (
                <button
                  key={reason}
                  className="w-full py-2 bg-[#2a2a2a] text-white rounded-lg hover:bg-[#333] transition-colors text-left px-4"
                >
                  {reason}
                </button>
              ))}
            </div>

            <button
              onClick={() => setShowReportModal(false)}
              className="w-full py-2 bg-[#2a2a2a] text-white rounded-lg hover:bg-[#333] transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* TikTok Modal */}
      {showTikTokModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#1a1a1a] rounded-lg max-w-md w-full p-6 border border-gray-800">
            <h3 className="text-xl font-bold text-white mb-4">Post to TikTok</h3>
            
            <textarea
              placeholder="Add a caption..."
              className="w-full h-32 bg-[#0a0a0a] text-white rounded-lg p-4 border border-gray-800 focus:border-[#7c3aed] focus:outline-none resize-none mb-4"
              maxLength={150}
              value={tiktokCaption}
              onChange={(e) => setTiktokCaption(e.target.value)}
            />

            <div className="flex items-center space-x-2 mb-6">
              <input
                type="checkbox"
                id="original-audio"
                checked={useOriginalAudio}
                onChange={(e) => setUseOriginalAudio(e.target.checked)}
                className="w-4 h-4"
              />
              <label htmlFor="original-audio" className="text-white text-sm">
                Use as original audio
              </label>
            </div>

            <div className="flex space-x-4">
              <button
                onClick={handlePostToTikTok}
                disabled={postingToTikTok}
                className="flex-1 py-2 bg-[#7c3aed] text-white rounded-lg font-medium hover:bg-[#6d28d9] disabled:opacity-50 transition-colors"
              >
                {postingToTikTok ? 'Posting...' : 'Post'}
              </button>
              <button
                onClick={() => setShowTikTokModal(false)}
                className="flex-1 py-2 bg-[#2a2a2a] text-white rounded-lg font-medium hover:bg-[#333] transition-colors"
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
