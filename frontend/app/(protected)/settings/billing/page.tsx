'use client';

import { useState, useEffect } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { useAuth } from '@clerk/nextjs';
import { ArrowLeft, CreditCard, Shield, ExternalLink, Zap, AlertTriangle, Loader2 } from 'lucide-react';

interface SubscriptionStatus {
  plan: string;
  status: string;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  features: string[];
}

interface UsageInfo {
  subscription_tier: string;
  current_hour: {
    generations: { used: number; limit: number; remaining: number };
    remixes: { used: number; limit: number; remaining: number };
  };
  current_month: {
    total_generations: number;
    shield_whitelists: number;
  };
  api_limit_per_minute: number;
}

export default function BillingSettingsPage() {
  const { getToken } = useAuth();
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);

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
      throw new Error('Failed to fetch api');
    }
    return res.json();
  };

  const { data: subscription, error: subError, isLoading: subLoading } = useSWR<SubscriptionStatus>(
    authToken ? ['/api/subscriptions/status', authToken] : null,
    swrFetcher
  );

  const { data: usage, error: usageError, isLoading: usageLoading } = useSWR<UsageInfo>(
    authToken ? ['/api/analytics/usage', authToken] : null,
    swrFetcher
  );

  const handleManageBilling = async () => {
    setPortalLoading(true);
    try {
      const response = await fetch('/api/subscriptions/portal', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (data.url) {
          window.location.href = data.url;
        } else {
          alert('Failed to resolve billing portal redirect URL');
        }
      } else {
        const err = await response.json();
        alert(err.detail || 'Failed to open billing portal');
      }
    } catch (err) {
      console.error('Portal redirect error:', err);
      alert('Network error while opening billing portal');
    } finally {
      setPortalLoading(false);
    }
  };

  const loading = subLoading || usageLoading;

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <Loader2 className="w-12 h-12 text-[#7c3aed] animate-spin" />
      </div>
    );
  }

  const tierNameMap: Record<string, string> = {
    free: 'Remixa Free',
    pro: 'Remixa Pro',
    business: 'Remixa Business',
  };

  const currentPlan = subscription?.plan || 'free';
  const planName = tierNameMap[currentPlan] || currentPlan;

  // Calcul percentages for progress bars
  const genHourUsed = usage?.current_hour.generations.used || 0;
  const genHourLimit = usage?.current_hour.generations.limit || 1;
  const genPercentage = Math.min(100, (genHourUsed / genHourLimit) * 100);

  const remixHourUsed = usage?.current_hour.remixes.used || 0;
  const remixHourLimit = usage?.current_hour.remixes.limit || 1;
  const remixPercentage = Math.min(100, (remixHourUsed / remixHourLimit) * 100);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#1a1a1a]/80 backdrop-blur-md border-b border-gray-800">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/profile" className="flex items-center space-x-2 text-gray-400 hover:text-white transition-colors">
            <ArrowLeft className="w-5 h-5" />
            <span>Back to Profile</span>
          </Link>
          <h1 className="text-xl font-bold">Billing & Subscriptions</h1>
          <div className="w-24"></div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-12 max-w-4xl">
        {/* Tier Status Info Card */}
        <div className="bg-[#1a1a1a] rounded-2xl border border-gray-800 p-8 mb-8 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-5 pointer-events-none">
            <CreditCard className="w-48 h-48" />
          </div>

          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div>
              <span className="text-gray-400 text-sm uppercase tracking-wider font-bold">Current Subscription</span>
              <h2 className="text-3xl font-black mt-1 bg-clip-text text-transparent bg-gradient-to-r from-[#7c3aed] to-[#ec4899]">
                {planName}
              </h2>
              {subscription?.current_period_end && (
                <p className="text-gray-400 text-xs mt-2">
                  Next renewal on: {new Date(subscription.current_period_end).toLocaleDateString()}
                  {subscription.cancel_at_period_end && <span className="text-red-400 font-bold ml-1.5">(Cancelling at end of period)</span>}
                </p>
              )}
            </div>

            <div className="flex flex-col sm:flex-row gap-4">
              {currentPlan !== 'free' ? (
                <button
                  onClick={handleManageBilling}
                  disabled={portalLoading}
                  className="px-6 py-3 bg-[#2a2a2a] hover:bg-[#333] text-white font-bold rounded-xl flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
                >
                  {portalLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <ExternalLink className="w-4 h-4" />
                      <span>Manage Stripe Billing</span>
                    </>
                  )}
                </button>
              ) : (
                <Link
                  href="/pricing"
                  className="px-8 py-3 bg-gradient-to-r from-[#7c3aed] to-[#ec4899] text-white font-bold rounded-xl hover:opacity-90 transition-all flex items-center justify-center space-x-2 shadow-lg"
                >
                  <Zap className="w-4 h-4" />
                  <span>Upgrade Plan</span>
                </Link>
              )}
            </div>
          </div>
        </div>

        {/* Telemetry Usage Progress */}
        <div className="bg-[#121212] border border-gray-800 rounded-2xl p-8 mb-8">
          <h3 className="text-xl font-bold mb-6 flex items-center space-x-2">
            <Zap className="w-5 h-5 text-[#7c3aed]" />
            <span>Hourly / Monthly Compute Limits</span>
          </h3>

          <div className="space-y-6">
            {/* Generations progress */}
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-300 font-medium">Track Generations (Current hour)</span>
                <span className="text-white font-bold">
                  {genHourUsed} / {genHourLimit}
                </span>
              </div>
              <div className="w-full bg-[#222] rounded-full h-3.5 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-[#7c3aed] to-[#ec4899] h-full rounded-full transition-all duration-500"
                  style={{ width: `${genPercentage}%` }}
                ></div>
              </div>
            </div>

            {/* Remixes progress */}
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-300 font-medium">Remixes Generated (Current hour)</span>
                <span className="text-white font-bold">
                  {remixHourUsed} / {remixHourLimit}
                </span>
              </div>
              <div className="w-full bg-[#222] rounded-full h-3.5 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-[#7c3aed] to-[#ec4899] h-full rounded-full transition-all duration-500"
                  style={{ width: `${remixPercentage}%` }}
                ></div>
              </div>
            </div>

            {/* Monthly and API stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-6 border-t border-gray-800">
              <div className="bg-[#1a1a1a] rounded-xl p-5 border border-gray-800">
                <span className="text-xs text-gray-400 font-semibold uppercase block">Generations This Month</span>
                <span className="text-2xl font-black text-white mt-1 block">
                  {usage?.current_month.total_generations || 0}
                </span>
              </div>
              
              <div className="bg-[#1a1a1a] rounded-xl p-5 border border-gray-800">
                <span className="text-xs text-gray-400 font-semibold uppercase block">Shield Whitelisted Videos</span>
                <span className="text-2xl font-black text-white mt-1 block">
                  {usage?.current_month.shield_whitelists || 0}
                </span>
              </div>

              <div className="bg-[#1a1a1a] rounded-xl p-5 border border-gray-800">
                <span className="text-xs text-gray-400 font-semibold uppercase block">API Request Limit</span>
                <span className="text-2xl font-black text-white mt-1 block">
                  {usage?.api_limit_per_minute || 0} req/min
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Feature inclusions */}
        {subscription?.features && subscription.features.length > 0 && (
          <div className="bg-[#1a1a1a] border border-gray-800 rounded-2xl p-8">
            <h3 className="text-lg font-bold mb-4 flex items-center space-x-2">
              <Shield className="w-5 h-5 text-green-400" />
              <span>Features Included in Your Tier</span>
            </h3>
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {subscription.features.map((feature, index) => (
                <li key={index} className="flex items-center text-sm text-gray-300">
                  <span className="w-2 h-2 rounded-full bg-[#7c3aed] mr-3"></span>
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
