'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Settings, Share2, UserPlus, UserCheck } from 'lucide-react';
import TapeCard from '../../components/TapeCard';
import StreakBadge from '../../components/StreakBadge';

interface Profile {
  id: string;
  username: string;
  bio?: string;
  avatar_url?: string;
  created_at: string;
  stats: {
    tapes_count: number;
    remixes_count: number;
    total_earnings: number;
    followers_count: number;
    following_count: number;
  };
  streak_days: number;
  is_following: boolean;
  is_own_profile: boolean;
  invite_codes?: string[];
}

type TabType = 'tapes' | 'remixes' | 'liked';

export default function ProfilePage() {
  const params = useParams();
  const userId = params.id as string;

  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('tapes');
  const [tapes, setTapes] = useState<any[]>([]);
  const [tapesLoading, setTapesLoading] = useState(false);
  const [following, setFollowing] = useState(false);

  useEffect(() => {
    fetchProfile();
  }, [userId]);

  useEffect(() => {
    fetchTapes();
  }, [activeTab, userId]);

  const fetchProfile = async () => {
    try {
      const response = await fetch(`/api/users/${userId}`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });
      const data = await response.json();
      setProfile(data);
      setFollowing(data.is_following);
    } catch (error) {
      console.error('Failed to load profile:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchTapes = async () => {
    setTapesLoading(true);
    try {
      const endpoint = activeTab === 'tapes' ? 'tapes' : activeTab === 'remixes' ? 'remixes' : 'liked';
      const response = await fetch(`/api/users/${userId}/${endpoint}`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });
      const data = await response.json();
      setTapes(data.tapes || []);
    } catch (error) {
      console.error('Failed to load tapes:', error);
    } finally {
      setTapesLoading(false);
    }
  };

  const handleFollow = async () => {
    try {
      const response = await fetch(`/api/users/${userId}/follow`, {
        method: following ? 'DELETE' : 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });

      if (response.ok) {
        setFollowing(!following);
        if (profile) {
          setProfile({
            ...profile,
            stats: {
              ...profile.stats,
              followers_count: following
                ? profile.stats.followers_count - 1
                : profile.stats.followers_count + 1,
            },
          });
        }
      }
    } catch (error) {
      console.error('Failed to follow/unfollow:', error);
    }
  };

  const handleShare = async () => {
    const shareUrl = `${window.location.origin}/profile/${userId}`;
    
    if (navigator.share) {
      try {
        await navigator.share({
          title: `Check out ${profile?.username}'s profile`,
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

  if (!profile) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-2">User not found</h2>
          <Link href="/dashboard" className="text-[#7c3aed] hover:underline">
            Back to Dashboard
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
            <span>Back to Dashboard</span>
          </Link>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Profile Header */}
        <div className="bg-[#1a1a1a] rounded-lg p-8 mb-8">
          <div className="flex flex-col md:flex-row items-start md:items-center space-y-6 md:space-y-0 md:space-x-8">
            {/* Avatar */}
            <div className="w-32 h-32 rounded-full bg-gradient-to-br from-[#7c3aed] to-[#ec4899] flex items-center justify-center text-white text-5xl font-bold flex-shrink-0">
              {profile.avatar_url ? (
                <img
                  src={profile.avatar_url}
                  alt={profile.username}
                  className="w-full h-full rounded-full object-cover"
                />
              ) : (
                profile.username.charAt(0).toUpperCase()
              )}
            </div>

            {/* Info */}
            <div className="flex-1">
              <div className="flex items-center space-x-4 mb-4">
                <h1 className="text-3xl font-bold text-white">{profile.username}</h1>
                {profile.streak_days > 0 && <StreakBadge days={profile.streak_days} size="lg" />}
              </div>

              {profile.bio && (
                <p className="text-gray-400 mb-4">{profile.bio}</p>
              )}

              <div className="flex items-center space-x-6 text-sm mb-6">
                <div>
                  <span className="text-white font-bold">{profile.stats.tapes_count}</span>
                  <span className="text-gray-400 ml-1">tapes</span>
                </div>
                <div>
                  <span className="text-white font-bold">{profile.stats.remixes_count}</span>
                  <span className="text-gray-400 ml-1">remixes</span>
                </div>
                <div>
                  <span className="text-white font-bold">€{profile.stats.total_earnings.toFixed(2)}</span>
                  <span className="text-gray-400 ml-1">earned</span>
                </div>
                <div>
                  <span className="text-white font-bold">{profile.stats.followers_count}</span>
                  <span className="text-gray-400 ml-1">followers</span>
                </div>
                <div>
                  <span className="text-white font-bold">{profile.stats.following_count}</span>
                  <span className="text-gray-400 ml-1">following</span>
                </div>
              </div>

              {/* Actions */}
              <div className="flex space-x-4">
                {profile.is_own_profile ? (
                  <>
                    <Link
                      href="/settings"
                      className="px-6 py-2 bg-[#7c3aed] text-white rounded-lg font-medium hover:bg-[#6d28d9] transition-colors flex items-center space-x-2"
                    >
                      <Settings className="w-4 h-4" />
                      <span>Edit Profile</span>
                    </Link>
                    <button
                      onClick={handleShare}
                      className="px-6 py-2 bg-[#2a2a2a] text-white rounded-lg font-medium hover:bg-[#333] transition-colors flex items-center space-x-2"
                    >
                      <Share2 className="w-4 h-4" />
                      <span>Share</span>
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={handleFollow}
                      className={`px-6 py-2 rounded-lg font-medium transition-colors flex items-center space-x-2 ${
                        following
                          ? 'bg-[#2a2a2a] text-white hover:bg-[#333]'
                          : 'bg-[#7c3aed] text-white hover:bg-[#6d28d9]'
                      }`}
                    >
                      {following ? (
                        <>
                          <UserCheck className="w-4 h-4" />
                          <span>Following</span>
                        </>
                      ) : (
                        <>
                          <UserPlus className="w-4 h-4" />
                          <span>Follow</span>
                        </>
                      )}
                    </button>
                    <button
                      onClick={handleShare}
                      className="px-6 py-2 bg-[#2a2a2a] text-white rounded-lg font-medium hover:bg-[#333] transition-colors flex items-center space-x-2"
                    >
                      <Share2 className="w-4 h-4" />
                      <span>Share</span>
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Invite Codes (own profile only) */}
          {profile.is_own_profile && profile.invite_codes && profile.invite_codes.length > 0 && (
            <div className="mt-8 pt-8 border-t border-gray-800">
              <h3 className="text-white font-bold mb-4">Your Invite Codes</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {profile.invite_codes.map((code, idx) => (
                  <div key={idx} className="bg-[#0a0a0a] rounded-lg p-4">
                    <div className="text-gray-400 text-xs mb-2">Code {idx + 1}</div>
                    <div className="font-mono text-white text-lg">{code}</div>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(code);
                        alert('Code copied!');
                      }}
                      className="mt-2 text-[#7c3aed] text-sm hover:underline"
                    >
                      Copy
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className="flex space-x-2 mb-6 overflow-x-auto">
          <button
            onClick={() => setActiveTab('tapes')}
            className={`px-6 py-3 rounded-lg font-medium transition-colors whitespace-nowrap ${
              activeTab === 'tapes'
                ? 'bg-[#7c3aed] text-white'
                : 'bg-[#1a1a1a] text-gray-400 hover:text-white'
            }`}
          >
            Tapes ({profile.stats.tapes_count})
          </button>
          <button
            onClick={() => setActiveTab('remixes')}
            className={`px-6 py-3 rounded-lg font-medium transition-colors whitespace-nowrap ${
              activeTab === 'remixes'
                ? 'bg-[#7c3aed] text-white'
                : 'bg-[#1a1a1a] text-gray-400 hover:text-white'
            }`}
          >
            Remixes ({profile.stats.remixes_count})
          </button>
          <button
            onClick={() => setActiveTab('liked')}
            className={`px-6 py-3 rounded-lg font-medium transition-colors whitespace-nowrap ${
              activeTab === 'liked'
                ? 'bg-[#7c3aed] text-white'
                : 'bg-[#1a1a1a] text-gray-400 hover:text-white'
            }`}
          >
            Liked
          </button>
        </div>

        {/* Tapes Grid */}
        {tapesLoading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#7c3aed]"></div>
          </div>
        ) : tapes.length === 0 ? (
          <div className="text-center py-20 text-gray-400">
            <p>No {activeTab} yet</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {tapes.map((tape) => (
              <TapeCard key={tape.id} tape={tape} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
