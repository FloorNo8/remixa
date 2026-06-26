'use client';

import { useState, useEffect } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { ArrowLeft, TrendingUp, DollarSign, Download, ExternalLink } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useAuth } from '@clerk/nextjs';

interface Transaction {
  id: string;
  type: 'remix_fee' | 'royalty' | 'withdrawal';
  amount: number;
  from_user?: {
    id: string;
    username: string;
  };
  tape?: {
    id: string;
    prompt: string;
  };
  created_at: string;
  status: 'completed' | 'pending' | 'failed';
}

interface EarningsData {
  total_earned: number;
  pending_balance: number;
  total_remixes: number;
  this_month_earnings: number;
  chart_data: Array<{ date: string; earnings: number }>;
  recent_transactions: Transaction[];
  stripe_connected: boolean;
  can_withdraw: boolean;
}

export default function EarningsPage() {
  const [withdrawing, setWithdrawing] = useState(false);
  const [showWithdrawModal, setShowWithdrawModal] = useState(false);
  const { getToken } = useAuth();
  const [authToken, setAuthToken] = useState<string | null>(null);

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
      const error: any = new Error('An error occurred while fetching the data.');
      error.info = await res.json().catch(() => ({}));
      error.status = res.status;
      throw error;
    }
    return res.json();
  };

  const { data, error, isLoading: loading, mutate } = useSWR<EarningsData>(
    authToken ? ['/api/earnings', authToken] : null,
    swrFetcher,
    {
      refreshInterval: 60000, // Refresh every minute
      revalidateOnFocus: true,
    }
  );

  const fetchEarnings = () => mutate();

  const handleWithdraw = async () => {
    if (!data?.can_withdraw) return;

    setWithdrawing(true);
    try {
      const token = await getToken();
      const response = await fetch('/api/earnings/withdraw', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        setShowWithdrawModal(false);
        fetchEarnings(); // Refresh data
        alert('Withdrawal initiated! Funds will arrive in 2-5 business days.');
      } else {
        const error = await response.json();
        alert(error.detail || 'Withdrawal failed');
      }
    } catch (error) {
      console.error('Withdrawal error:', error);
      alert('Withdrawal failed');
    } finally {
      setWithdrawing(false);
    }
  };

  const handleConnectStripe = async () => {
    try {
      const token = await getToken();
      const response = await fetch('/api/stripe/connect', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const resData = await response.json();
        if (resData.onboarding_url) {
          window.location.href = resData.onboarding_url;
        } else {
          alert('Failed to obtain onboarding URL.');
        }
      } else {
        const error = await response.json();
        alert(error.detail || 'Stripe connection initiation failed');
      }
    } catch (error) {
      console.error('Stripe connection error:', error);
      alert('Stripe connection failed');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#7c3aed]"></div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-2">Failed to load earnings</h2>
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
          <div className="flex items-center justify-between">
            <Link href="/dashboard" className="flex items-center space-x-2 text-gray-400 hover:text-white">
              <ArrowLeft className="w-5 h-5" />
              <span>Back to Dashboard</span>
            </Link>
            <h1 className="text-2xl font-bold text-white">Earnings</h1>
            <div className="w-32"></div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="bg-[#1a1a1a] rounded-lg p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm">Total Earned</span>
              <DollarSign className="w-5 h-5 text-green-400" />
            </div>
            <div className="text-3xl font-bold text-white">€{data.total_earned.toFixed(2)}</div>
            <div className="text-gray-500 text-sm mt-1">All time</div>
          </div>

          <div className="bg-[#1a1a1a] rounded-lg p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm">Pending Balance</span>
              <TrendingUp className="w-5 h-5 text-[#7c3aed]" />
            </div>
            <div className="text-3xl font-bold text-white">€{data.pending_balance.toFixed(2)}</div>
            <div className="text-gray-500 text-sm mt-1">Available to withdraw</div>
          </div>

          <div className="bg-[#1a1a1a] rounded-lg p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm">Total Remixes</span>
              <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
            </div>
            <div className="text-3xl font-bold text-white">{data.total_remixes}</div>
            <div className="text-gray-500 text-sm mt-1">Of your tapes</div>
          </div>

          <div className="bg-[#1a1a1a] rounded-lg p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm">This Month</span>
              <svg className="w-5 h-5 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <div className="text-3xl font-bold text-white">€{data.this_month_earnings.toFixed(2)}</div>
            <div className="text-gray-500 text-sm mt-1">June 2026</div>
          </div>
        </div>

        {/* Stripe Connect Status */}
        {!data.stripe_connected && (
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-6 mb-8">
            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0 w-12 h-12 bg-yellow-500/20 rounded-lg flex items-center justify-center">
                <ExternalLink className="w-6 h-6 text-yellow-400" />
              </div>
              <div className="flex-1">
                <h3 className="text-white font-bold mb-2">Connect Stripe to Withdraw</h3>
                <p className="text-gray-400 text-sm mb-4">
                  You need to connect your Stripe account to receive payouts. This is required by EU payment regulations.
                </p>
                <button
                  onClick={handleConnectStripe}
                  className="px-6 py-2 bg-yellow-500 text-black rounded-lg font-medium hover:bg-yellow-400 transition-colors"
                >
                  Connect Stripe Account
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Earnings Chart */}
        <div className="bg-[#1a1a1a] rounded-lg p-6 mb-8">
          <h3 className="text-xl font-bold text-white mb-6">Earnings Over Time</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.chart_data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="date" stroke="#888" />
              <YAxis stroke="#888" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1a1a1a',
                  border: '1px solid #333',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: '#fff' }}
              />
              <Line
                type="monotone"
                dataKey="earnings"
                stroke="#7c3aed"
                strokeWidth={2}
                dot={{ fill: '#7c3aed', r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Withdraw Button */}
        <div className="bg-[#1a1a1a] rounded-lg p-6 mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xl font-bold text-white mb-2">Withdraw Earnings</h3>
              <p className="text-gray-400 text-sm">
                Minimum withdrawal: €20.00 • Processing time: 2-5 business days
              </p>
            </div>
            <button
              onClick={() => setShowWithdrawModal(true)}
              disabled={!data.can_withdraw || !data.stripe_connected}
              className="px-8 py-3 bg-[#7c3aed] text-white rounded-lg font-bold hover:bg-[#6d28d9] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Withdraw €{data.pending_balance.toFixed(2)}
            </button>
          </div>
        </div>

        {/* Recent Transactions */}
        <div className="bg-[#1a1a1a] rounded-lg p-6">
          <h3 className="text-xl font-bold text-white mb-6">Recent Transactions</h3>
          
          {data.recent_transactions.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <DollarSign className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No transactions yet</p>
            </div>
          ) : (
            <div className="space-y-4">
              {data.recent_transactions.map((tx) => (
                <div key={tx.id} className="flex items-center justify-between p-4 bg-[#0a0a0a] rounded-lg">
                  <div className="flex items-center space-x-4">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      tx.type === 'remix_fee' ? 'bg-green-500/20' :
                      tx.type === 'royalty' ? 'bg-blue-500/20' :
                      'bg-red-500/20'
                    }`}>
                      {tx.type === 'remix_fee' ? (
                        <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                      ) : tx.type === 'royalty' ? (
                        <TrendingUp className="w-5 h-5 text-blue-400" />
                      ) : (
                        <Download className="w-5 h-5 text-red-400" />
                      )}
                    </div>
                    
                    <div>
                      <div className="text-white font-medium">
                        {tx.type === 'remix_fee' && 'Remix Fee'}
                        {tx.type === 'royalty' && 'Royalty Payment'}
                        {tx.type === 'withdrawal' && 'Withdrawal'}
                      </div>
                      <div className="text-gray-400 text-sm">
                        {tx.from_user && `from ${tx.from_user.username}`}
                        {tx.tape && (
                          <Link href={`/tape/${tx.tape.id}`} className="hover:text-white">
                            {' • '}{tx.tape.prompt.substring(0, 30)}...
                          </Link>
                        )}
                        {' • '}{new Date(tx.created_at).toLocaleDateString()}
                      </div>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className={`text-lg font-bold ${
                      tx.type === 'withdrawal' ? 'text-red-400' : 'text-green-400'
                    }`}>
                      {tx.type === 'withdrawal' ? '−' : '+'}€{tx.amount.toFixed(2)}
                    </div>
                    <div className={`text-xs ${
                      tx.status === 'completed' ? 'text-green-400' :
                      tx.status === 'pending' ? 'text-yellow-400' :
                      'text-red-400'
                    }`}>
                      {tx.status}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Withdraw Confirmation Modal */}
      {showWithdrawModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#1a1a1a] rounded-lg max-w-md w-full p-6">
            <h3 className="text-xl font-bold text-white mb-4">Confirm Withdrawal</h3>
            
            <div className="bg-[#0a0a0a] rounded-lg p-4 mb-6">
              <div className="flex justify-between mb-2">
                <span className="text-gray-400">Amount</span>
                <span className="text-white font-bold">€{data.pending_balance.toFixed(2)}</span>
              </div>
              <div className="flex justify-between mb-2">
                <span className="text-gray-400">Processing Fee</span>
                <span className="text-white">€0.00</span>
              </div>
              <div className="border-t border-gray-800 my-2"></div>
              <div className="flex justify-between">
                <span className="text-white font-bold">You'll Receive</span>
                <span className="text-green-400 font-bold">€{data.pending_balance.toFixed(2)}</span>
              </div>
            </div>

            <p className="text-gray-400 text-sm mb-6">
              Funds will be transferred to your connected Stripe account within 2-5 business days.
            </p>

            <div className="flex space-x-4">
              <button
                onClick={handleWithdraw}
                disabled={withdrawing}
                className="flex-1 py-3 bg-[#7c3aed] text-white rounded-lg font-bold hover:bg-[#6d28d9] disabled:opacity-50 transition-colors"
              >
                {withdrawing ? 'Processing...' : 'Confirm Withdrawal'}
              </button>
              <button
                onClick={() => setShowWithdrawModal(false)}
                disabled={withdrawing}
                className="flex-1 py-3 bg-[#2a2a2a] text-white rounded-lg font-bold hover:bg-[#333] transition-colors"
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
