'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { Play, Pause, Heart, Share2, MoreVertical } from 'lucide-react';
import WaveformPlayer from './WaveformPlayer';
import C2PABadge from './C2PABadge';
import StreakBadge from './StreakBadge';

interface Tape {
  id: string;
  prompt: string;
  audio_url: string;
  waveform_data?: number[];
  creator: {
    id: string;
    username: string;
    avatar_url?: string;
  };
  remix_count: number;
  total_earnings: number;
  likes_count: number;
  is_liked: boolean;
  created_at: string;
  has_c2pa: boolean;
  parent_id?: string;
}

interface TapeCardProps {
  tape: Tape;
}

export default function TapeCard({ tape }: TapeCardProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLiked, setIsLiked] = useState(tape.is_liked);
  const [likesCount, setLikesCount] = useState(tape.likes_count);
  const [showMenu, setShowMenu] = useState(false);
  const waveformRef = useRef<any>(null);

  const handlePlayPause = () => {
    if (waveformRef.current) {
      if (isPlaying) {
        waveformRef.current.pause();
      } else {
        waveformRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleLike = async () => {
    try {
      const response = await fetch(`/api/tapes/${tape.id}/like`, {
        method: isLiked ? 'DELETE' : 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (response.ok) {
        setIsLiked(!isLiked);
        setLikesCount(prev => isLiked ? prev - 1 : prev + 1);
      }
    } catch (error) {
      console.error('Failed to like tape:', error);
    }
  };

  const handleShare = async () => {
    const shareUrl = `${window.location.origin}/tape/${tape.id}`;
    
    if (navigator.share) {
      try {
        await navigator.share({
          title: `Check out this tape: ${tape.prompt}`,
          url: shareUrl,
        });
      } catch (error) {
        // User cancelled share
      }
    } else {
      // Fallback: copy to clipboard
      await navigator.clipboard.writeText(shareUrl);
      alert('Link copied to clipboard!');
    }
  };

  return (
    <div className="bg-[#1a1a1a] rounded-lg overflow-hidden hover:bg-[#222] transition-colors">
      {/* Header */}
      <div className="p-4 flex items-center justify-between">
        <Link href={`/profile/${tape.creator.id}`} className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-full bg-[#7c3aed] flex items-center justify-center text-white font-bold">
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
            <div className="text-gray-400 text-sm">
              {new Date(tape.created_at).toLocaleDateString()}
            </div>
          </div>
        </Link>

        <div className="relative">
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="text-gray-400 hover:text-white p-2"
          >
            <MoreVertical className="w-5 h-5" />
          </button>
          
          {showMenu && (
            <div className="absolute right-0 mt-2 w-48 bg-[#2a2a2a] rounded-lg shadow-lg py-2 z-10">
              <button className="w-full px-4 py-2 text-left text-white hover:bg-[#333] text-sm">
                Add to playlist
              </button>
              <button className="w-full px-4 py-2 text-left text-white hover:bg-[#333] text-sm">
                Download
              </button>
              <button className="w-full px-4 py-2 text-left text-red-400 hover:bg-[#333] text-sm">
                Report
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Waveform */}
      <div className="relative px-4 pb-4">
        <div className="relative bg-[#0a0a0a] rounded-lg p-4">
          <WaveformPlayer
            ref={waveformRef}
            audioUrl={tape.audio_url}
            waveformData={tape.waveform_data}
            onPlayStateChange={setIsPlaying}
          />
          
          {/* Play/Pause Overlay */}
          <button
            onClick={handlePlayPause}
            className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-16 h-16 bg-[#7c3aed] rounded-full flex items-center justify-center hover:bg-[#6d28d9] transition-colors shadow-lg"
          >
            {isPlaying ? (
              <Pause className="w-8 h-8 text-white" />
            ) : (
              <Play className="w-8 h-8 text-white ml-1" />
            )}
          </button>
        </div>
      </div>

      {/* Prompt */}
      <div className="px-4 pb-3">
        <p className="text-white text-sm line-clamp-2">{tape.prompt}</p>
      </div>

      {/* Stats & Actions */}
      <div className="px-4 pb-4 flex items-center justify-between">
        <div className="flex items-center space-x-4 text-sm">
          <div className="flex items-center space-x-1 text-gray-400">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
            </svg>
            <span>{tape.remix_count}</span>
          </div>
          
          <div className="flex items-center space-x-1 text-gray-400">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>€{tape.total_earnings.toFixed(2)}</span>
          </div>

          {tape.has_c2pa && <C2PABadge tapeId={tape.id} />}
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={handleLike}
            className={`flex items-center space-x-1 px-3 py-1.5 rounded-lg transition-colors ${
              isLiked
                ? 'bg-red-500/20 text-red-400'
                : 'bg-[#2a2a2a] text-gray-400 hover:text-white'
            }`}
          >
            <Heart className={`w-4 h-4 ${isLiked ? 'fill-current' : ''}`} />
            <span className="text-sm">{likesCount}</span>
          </button>

          <button
            onClick={handleShare}
            className="p-2 bg-[#2a2a2a] text-gray-400 hover:text-white rounded-lg transition-colors"
          >
            <Share2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Remix Button */}
      <div className="px-4 pb-4">
        <Link
          href={`/create?parent=${tape.id}`}
          className="block w-full py-2.5 bg-[#7c3aed] text-white text-center rounded-lg font-medium hover:bg-[#6d28d9] transition-colors"
        >
          Remix This Tape
        </Link>
      </div>

      {/* Parent Indicator */}
      {tape.parent_id && (
        <div className="px-4 pb-4">
          <Link
            href={`/tape/${tape.parent_id}`}
            className="flex items-center space-x-2 text-sm text-gray-400 hover:text-white"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
            </svg>
            <span>Remixed from original</span>
          </Link>
        </div>
      )}
    </div>
  );
}
