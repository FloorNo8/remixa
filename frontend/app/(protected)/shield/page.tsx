'use client';

import { useState, useEffect } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { useAuth } from '@clerk/nextjs';
import { Shield, ArrowLeft, Plus, CheckCircle, AlertCircle, Trash2, Search, Zap, Loader2, ExternalLink } from 'lucide-react';

interface WhitelistEntry {
  id: string;
  platform: 'youtube' | 'tiktok' | 'instagram';
  video_url: string;
  status: string;
  whitelisted_at: string;
  generation_id: string;
}

interface ShieldReport {
  platforms: Array<{ platform: string; total: number; active: number; inactive: number }>;
  recent_whitelists: WhitelistEntry[];
}

export default function ShieldPage() {
  const { getToken } = useAuth();
  const [authToken, setAuthToken] = useState<string | null>(null);

  // Form states
  const [genId, setGenId] = useState('');
  const [platform, setPlatform] = useState('youtube');
  const [videoUrl, setVideoUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Check state
  const [checkUrl, setCheckUrl] = useState('');
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState<any>(null);

  useEffect(() => {
    const fetchToken = async () => {
      try {
        const token = await getToken();
        setAuthToken(token);
      } catch (err) {
        console.error('Failed to get auth token:', err);
      }
    };
    fetchToken();
  }, [getToken]);

  const swrFetcher = async ([url, token]: [string, string | null]) => {
    const res = await fetch(url, {
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      const err = new Error(errorData.detail || 'API Fetch failed');
      (err as any).status = res.status;
      throw err;
    }
    return res.json();
  };

  // 1. Fetch Subscription Status to enforce gate
  const { data: subscription, error: subError } = useSWR<any>(
    authToken ? ['/api/subscriptions/status', authToken] : null,
    swrFetcher
  );

  // 2. Fetch Shield report data
  const isPremium = subscription?.plan === 'pro' || subscription?.plan === 'business';
  const { data: report, error: reportError, mutate: mutateReport, isLoading: reportLoading } = useSWR<ShieldReport>(
    authToken && isPremium ? ['/api/analytics/shield-report', authToken] : null,
    swrFetcher
  );

  const handleRegisterWhitelist = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!genId || !videoUrl) return;

    setSubmitting(true);
    try {
      const response = await fetch('/api/shield/whitelist', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          generation_id: genId.trim(),
          platform,
          video_url: videoUrl.trim(),
        }),
      });

      if (response.ok) {
        alert('Video URL successfully whitelisted under Remixa Shield!');
        setGenId('');
        setVideoUrl('');
        mutateReport();
      } else {
        const err = await response.json();
        alert(err.detail || 'Whitelisting failed');
      }
    } catch (err) {
      console.error(err);
      alert('Network error while registering whitelist');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteWhitelist = async (id: string) => {
    if (!confirm('Are you sure you want to remove this video from your whitelists? You will lose copyright protection.')) {
      return;
    }

    try {
      const response = await fetch(`/api/shield/whitelist/${id}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      if (response.ok) {
        mutateReport();
      } else {
        const err = await response.json();
        alert(err.detail || 'Failed to remove whitelist');
      }
    } catch (err) {
      console.error(err);
      alert('Failed to remove whitelist');
    }
  };

  const handleCheckUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!checkUrl) return;

    setChecking(true);
    setCheckResult(null);
    try {
      const response = await fetch(`/api/shield/whitelist/check?video_url=${encodeURIComponent(checkUrl.trim())}`);
      if (response.ok) {
        const data = await response.json();
        setCheckResult(data);
      } else {
        alert('Failed to check URL whitelist status.');
      }
    } catch (err) {
      console.error(err);
      alert('Error verifying URL status.');
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#1a1a1a]/80 backdrop-blur-md border-b border-gray-800">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/dashboard" className="flex items-center space-x-2 text-gray-400 hover:text-white transition-colors">
            <ArrowLeft className="w-5 h-5" />
            <span>Back to Dashboard</span>
          </Link>
          <div className="flex items-center space-x-2">
            <Shield className="w-6 h-6 text-[#7c3aed]" />
            <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-[#7c3aed] to-[#ec4899]">
              Remixa Shield Cockpit
            </span>
          </div>
          <div className="w-24"></div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-12 max-w-6xl">
        {/* Verification Check Tool (Publicly accessible section) */}
        <div className="bg-[#121212] border border-gray-800 rounded-2xl p-6 md:p-8 mb-12">
          <h2 className="text-xl font-black mb-2">Copyright Invariant Verification</h2>
          <p className="text-gray-400 text-sm mb-6">
            Input a video link to check if the sound license is verified and cleared of copyright muting risks.
          </p>

          <form onSubmit={handleCheckUrl} className="flex flex-col sm:flex-row gap-4 mb-6">
            <input
              type="url"
              required
              placeholder="e.g. https://www.youtube.com/watch?v=..."
              value={checkUrl}
              onChange={(e) => setCheckUrl(e.target.value)}
              className="flex-1 px-4 py-3 bg-[#1a1a1a] border border-gray-800 rounded-xl focus:outline-none focus:border-[#7c3aed] text-white"
            />
            <button
              type="submit"
              disabled={checking}
              className="px-6 py-3 bg-[#7c3aed] hover:bg-[#6d28d9] text-white font-bold rounded-xl flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
            >
              {checking ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  <span>Verify URL License</span>
                </>
              )}
            </button>
          </form>

          {checkResult && (
            <div
              className={`p-6 rounded-xl border flex items-start space-x-4 ${
                checkResult.cleared
                  ? 'bg-green-500/10 border-green-500/30 text-green-400'
                  : 'bg-red-500/10 border-red-500/30 text-red-400'
              }`}
            >
              {checkResult.cleared ? (
                <>
                  <CheckCircle className="w-8 h-8 flex-shrink-0" />
                  <div>
                    <h4 className="font-bold text-white text-lg">Verified Cleared</h4>
                    <p className="text-sm text-gray-400 mt-1">
                      This video is whitelisted and linked to a licensed generation. Platform Content ID is signaled to bypass muting.
                    </p>
                    <div className="text-xs text-gray-500 mt-3 font-mono">
                      Whitelist ID: {checkResult.id} • Registered: {new Date(checkResult.whitelisted_at).toLocaleString()}
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <AlertCircle className="w-8 h-8 flex-shrink-0" />
                  <div>
                    <h4 className="font-bold text-white text-lg">Mute Risk Warning</h4>
                    <p className="text-sm text-gray-400 mt-1">
                      {checkResult.reason} Please register this URL under your dashboard to apply protection.
                    </p>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Premium Gate: If User is Free Tier */}
        {!isPremium ? (
          <div className="bg-gradient-to-br from-[#7c3aed]/10 to-[#ec4899]/10 border border-[#7c3aed]/30 rounded-3xl p-12 text-center max-w-3xl mx-auto">
            <Shield className="w-16 h-16 text-[#7c3aed] mx-auto mb-6 animate-pulse" />
            <h2 className="text-3xl font-extrabold mb-4">Unlock Remixa Shield</h2>
            <p className="text-gray-300 text-sm leading-relaxed mb-8 max-w-lg mx-auto">
              Automated Whitelisting API registration is a premium service reserved for Pro and Business creators. 
              Upgrade today to protect your videos from copyright muting, copyright strikes, and content takedowns on TikTok, YouTube, and Instagram.
            </p>
            <Link
              href="/pricing"
              className="inline-flex items-center space-x-2 px-8 py-4 bg-gradient-to-r from-[#7c3aed] to-[#ec4899] text-white font-bold rounded-xl hover:opacity-90 transition-all shadow-lg"
            >
              <Zap className="w-5 h-5" />
              <span>Explore Upgrade Plans</span>
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Whitelist Registration Form */}
            <div className="lg:col-span-1">
              <div className="bg-[#1a1a1a] border border-gray-800 rounded-2xl p-6">
                <h3 className="text-lg font-bold mb-4 flex items-center space-x-2">
                  <Plus className="w-5 h-5 text-[#7c3aed]" />
                  <span>Register Video URL</span>
                </h3>
                
                <form onSubmit={handleRegisterWhitelist} className="space-y-4">
                  <div>
                    <label className="text-xs text-gray-400 font-bold block mb-1">Licensed Generation ID</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. e4d20914-49c..."
                      value={genId}
                      onChange={(e) => setGenId(e.target.value)}
                      className="w-full px-3 py-2 bg-[#0a0a0a] border border-gray-800 rounded-lg focus:outline-none focus:border-[#7c3aed] text-sm text-white"
                    />
                  </div>

                  <div>
                    <label className="text-xs text-gray-400 font-bold block mb-1">Target Platform</label>
                    <select
                      value={platform}
                      onChange={(e) => setPlatform(e.target.value)}
                      className="w-full px-3 py-2 bg-[#0a0a0a] border border-gray-800 rounded-lg focus:outline-none focus:border-[#7c3aed] text-sm text-white"
                    >
                      <option value="youtube">YouTube</option>
                      <option value="tiktok">TikTok</option>
                      <option value="instagram">Instagram</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-xs text-gray-400 font-bold block mb-1">Video Link (URL)</label>
                    <input
                      type="url"
                      required
                      placeholder="e.g. https://tiktok.com/@creator/video/..."
                      value={videoUrl}
                      onChange={(e) => setVideoUrl(e.target.value)}
                      className="w-full px-3 py-2 bg-[#0a0a0a] border border-gray-800 rounded-lg focus:outline-none focus:border-[#7c3aed] text-sm text-white"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={submitting}
                    className="w-full py-3 bg-gradient-to-r from-[#7c3aed] to-[#ec4899] text-white font-bold rounded-lg hover:opacity-90 transition-all flex items-center justify-center space-x-2 disabled:opacity-50"
                  >
                    {submitting ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <>
                        <Shield className="w-4 h-4" />
                        <span>Register Whitelist</span>
                      </>
                    )}
                  </button>
                </form>
              </div>
            </div>

            {/* Whitelisted Active List & Platform stats */}
            <div className="lg:col-span-2 space-y-8">
              {/* Platform breakdown */}
              <div className="grid grid-cols-3 gap-4">
                {['youtube', 'tiktok', 'instagram'].map((plat) => {
                  const platData = report?.platforms.find((p) => p.platform === plat);
                  return (
                    <div key={plat} className="bg-[#1a1a1a] border border-gray-800 rounded-xl p-5 capitalize">
                      <span className="text-xs text-gray-400 block font-semibold">{plat}</span>
                      <span className="text-3xl font-black mt-1 block">
                        {platData?.total || 0}
                      </span>
                      <span className="text-[10px] text-green-400 font-bold block mt-1">
                        {platData?.active || 0} active protection
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Whitelists Table */}
              <div className="bg-[#1a1a1a] border border-gray-800 rounded-2xl p-6">
                <h3 className="text-lg font-bold mb-6">Protected Whitelists</h3>
                
                {reportLoading ? (
                  <div className="flex justify-center py-12">
                    <Loader2 className="w-8 h-8 text-[#7c3aed] animate-spin" />
                  </div>
                ) : !report?.recent_whitelists || report.recent_whitelists.length === 0 ? (
                  <div className="text-center py-12 text-gray-400">
                    <Shield className="w-12 h-12 mx-auto mb-4 opacity-30" />
                    <p className="text-sm">No video URLs whitelisted yet.</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm text-gray-300">
                      <thead>
                        <tr className="border-b border-gray-800 text-xs uppercase text-gray-400 font-bold">
                          <th className="pb-3">Platform</th>
                          <th className="pb-3">Video Link</th>
                          <th className="pb-3">Added</th>
                          <th className="pb-3 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-800">
                        {report.recent_whitelists.map((entry) => (
                          <tr key={entry.id}>
                            <td className="py-4 capitalize font-semibold text-white">{entry.platform}</td>
                            <td className="py-4 max-w-[200px] truncate">
                              <a href={entry.video_url} target="_blank" rel="noreferrer" className="text-[#7c3aed] hover:underline flex items-center space-x-1 inline-flex max-w-full truncate">
                                <span className="truncate">{entry.video_url}</span>
                                <ExternalLink className="w-3.5 h-3.5 flex-shrink-0" />
                              </a>
                            </td>
                            <td className="py-4 text-xs text-gray-400">
                              {new Date(entry.whitelisted_at).toLocaleDateString()}
                            </td>
                            <td className="py-4 text-right">
                              <button
                                onClick={() => handleDeleteWhitelist(entry.id)}
                                className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors inline-flex"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
