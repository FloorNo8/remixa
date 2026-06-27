'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@clerk/nextjs';

interface User {
  id: string;
  email: string;
  username: string;
  created_at: string;
  role: string;
  banned: boolean;
  ban_reason?: string;
  balance: number;
  stripe_account_id?: string;
  generation_count: number;
  total_earnings: number;
}

export default function UserManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const { getToken } = useAuth();

  useEffect(() => {
    fetchUsers();
  }, []);

  async function fetchUsers(query?: string) {
    setLoading(true);
    try {
      const token = await getToken();
      const url = query
        ? `${process.env.NEXT_PUBLIC_API_URL}/api/admin/users/search?q=${encodeURIComponent(query)}&limit=50`
        : `${process.env.NEXT_PUBLIC_API_URL}/api/admin/users/search?limit=50`;

      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) throw new Error('Failed to fetch users');

      const data = await response.json();
      setUsers(data);
    } catch (error) {
      console.error('Error fetching users:', error);
    } finally {
      setLoading(false);
    }
  }

  async function handleBan(userId: string, reason: string) {
    try {
      const token = await getToken();
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/admin/users/${userId}/ban`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ reason }),
        }
      );

      if (!response.ok) throw new Error('Failed to ban user');

      // Refresh the list
      fetchUsers(searchQuery);
    } catch (error) {
      console.error('Error banning user:', error);
      alert('Failed to ban user');
    }
  }

  async function handleUnban(userId: string) {
    try {
      const token = await getToken();
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/admin/users/${userId}/unban`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) throw new Error('Failed to unban user');

      // Refresh the list
      fetchUsers(searchQuery);
    } catch (error) {
      console.error('Error unbanning user:', error);
      alert('Failed to unban user');
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    fetchUsers(searchQuery);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">User Management</h1>
        <p className="text-zinc-400">Search and manage user accounts</p>
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <input
          type="text"
          placeholder="Search by email, username, or ID..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="flex-1 px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600"
        />
        <button
          type="submit"
          className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
        >
          Search
        </button>
        {searchQuery && (
          <button
            type="button"
            onClick={() => {
              setSearchQuery('');
              fetchUsers();
            }}
            className="px-4 py-2 bg-zinc-800 text-white rounded-lg hover:bg-zinc-700 transition-colors"
          >
            Clear
          </button>
        )}
      </form>

      {/* Users List */}
      {loading ? (
        <div className="text-center py-12 text-zinc-400">Loading users...</div>
      ) : users.length === 0 ? (
        <div className="text-center py-12 text-zinc-400">No users found</div>
      ) : (
        <div className="space-y-4">
          {users.map((user) => (
            <UserCard
              key={user.id}
              user={user}
              onBan={handleBan}
              onUnban={handleUnban}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function UserCard({
  user,
  onBan,
  onUnban,
}: {
  user: User;
  onBan: (userId: string, reason: string) => void;
  onUnban: (userId: string) => void;
}) {
  const [showBanInput, setShowBanInput] = useState(false);
  const [banReason, setBanReason] = useState('');
  const [expanded, setExpanded] = useState(false);
  const [cogs, setCogs] = useState<any>(null);
  const [fetchingCogs, setFetchingCogs] = useState(false);
  const { getToken } = useAuth();

  const handleToggleExpand = async () => {
    const nextState = !expanded;
    setExpanded(nextState);

    if (nextState && !cogs) {
      setFetchingCogs(true);
      try {
        const token = await getToken();
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/admin/users/${user.id}/cogs`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (response.ok) {
          const data = await response.json();
          setCogs(data);
        } else {
          console.error('Failed to fetch COGS telemetry');
        }
      } catch (err) {
        console.error('Error fetching COGS:', err);
      } finally {
        setFetchingCogs(false);
      }
    }
  };

  return (
    <div
      className={`bg-zinc-900 rounded-lg p-6 border ${
        user.banned ? 'border-red-500/50' : 'border-zinc-800'
      }`}
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* User Info */}
        <div className="space-y-2">
          <div>
            <div className="text-sm text-zinc-400">Username</div>
            <div className="text-white font-medium">{user.username}</div>
          </div>
          <div>
            <div className="text-sm text-zinc-400">Email</div>
            <div className="text-white text-sm">{user.email}</div>
          </div>
          <div>
            <div className="text-sm text-zinc-400">User ID</div>
            <div className="text-zinc-500 text-xs font-mono">{user.id}</div>
          </div>
          <div>
            <div className="text-sm text-zinc-400">Role</div>
            <div className="text-white">
              <span
                className={`inline-block px-2 py-1 rounded text-xs ${
                  user.role === 'admin'
                    ? 'bg-purple-500/20 text-purple-400'
                    : user.role === 'moderator'
                    ? 'bg-blue-500/20 text-blue-400'
                    : user.role === 'creator'
                    ? 'bg-green-500/20 text-green-400'
                    : 'bg-zinc-700 text-zinc-300'
                }`}
              >
                {user.role}
              </span>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="space-y-2">
          <div>
            <div className="text-sm text-zinc-400">Joined</div>
            <div className="text-white">
              {new Date(user.created_at).toLocaleDateString()}
            </div>
          </div>
          <div>
            <div className="text-sm text-zinc-400">Generations</div>
            <div className="text-white">{user.generation_count}</div>
          </div>
          <div>
            <div className="text-sm text-zinc-400">Total Earnings</div>
            <div className="text-white font-mono">€{user.total_earnings.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-sm text-zinc-400">Balance</div>
            <div className="text-white font-mono">€{user.balance.toFixed(2)}</div>
          </div>
          {user.stripe_account_id && (
            <div>
              <div className="text-sm text-zinc-400">Stripe Connected</div>
              <div className="text-green-400">✓ Yes</div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="space-y-3">
          {user.banned ? (
            <div className="space-y-2">
              <div className="text-red-400 font-medium">🚫 Banned</div>
              {user.ban_reason && (
                <div className="text-sm text-zinc-400">
                  Reason: {user.ban_reason}
                </div>
              )}
              <button
                onClick={() => {
                  if (confirm('Unban this user?')) {
                    onUnban(user.id);
                  }
                }}
                className="w-full px-4 py-2 bg-green-500/20 text-green-400 rounded-lg hover:bg-green-500/30 transition-colors border border-green-500/50"
              >
                Unban User
              </button>
            </div>
          ) : showBanInput ? (
            <div className="space-y-2">
              <input
                type="text"
                placeholder="Reason for ban..."
                value={banReason}
                onChange={(e) => setBanReason(e.target.value)}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded text-white text-sm placeholder-zinc-500 focus:outline-none focus:border-zinc-600"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    if (banReason.trim()) {
                      onBan(user.id, banReason);
                      setBanReason('');
                      setShowBanInput(false);
                    }
                  }}
                  disabled={!banReason.trim()}
                  className="flex-1 px-3 py-2 bg-red-500 text-white rounded text-sm hover:bg-red-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Confirm Ban
                </button>
                <button
                  onClick={() => {
                    setBanReason('');
                    setShowBanInput(false);
                  }}
                  className="px-3 py-2 bg-zinc-800 text-white rounded text-sm hover:bg-zinc-700 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowBanInput(true)}
              className="w-full px-4 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors border border-red-500/50"
            >
              Ban User
            </button>
          )}

          <a
            href={`/profile/${user.id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="block w-full px-4 py-2 bg-zinc-800 text-white text-center rounded-lg hover:bg-zinc-700 transition-colors"
          >
            View Profile →
          </a>
        </div>
      </div>

      {/* Expandable Cost & Compute Telemetry Accordion */}
      <div className="mt-6 pt-6 border-t border-zinc-800">
        <button
          onClick={handleToggleExpand}
          className="flex items-center justify-between w-full text-left text-sm font-bold text-zinc-400 hover:text-white transition-colors"
        >
          <span className="flex items-center gap-2">
            <svg className={`w-4 h-4 text-purple-400 transition-transform ${expanded ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            ⚡ Compute & Cost Telemetry (FinOps)
          </span>
          <span className="text-xs text-zinc-500 font-normal">
            {expanded ? 'Collapse Detail' : 'Expand Economics'}
          </span>
        </button>

        {expanded && (
          <div className="mt-4 space-y-4">
            {fetchingCogs ? (
              <div className="text-zinc-500 text-xs animate-pulse">Calculating user unit economics...</div>
            ) : !cogs ? (
              <div className="text-red-400 text-xs">Failed to load telemetry stats.</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-zinc-950 border border-zinc-800/80 rounded-lg p-4">
                
                {/* Left Side: Loudness & GPU Meters */}
                <div className="space-y-4">
                  {/* GPU Seconds & Compute Limit */}
                  <div>
                    <div className="flex justify-between items-center text-xs text-zinc-400 mb-1.5 font-semibold">
                      <span>Total Replicate GPU Compute</span>
                      <span className="text-purple-400 font-mono">
                        {(cogs.compute_stats.gpu_seconds / 60).toFixed(1)} mins ({cogs.compute_stats.gpu_seconds.toFixed(0)}s)
                      </span>
                    </div>
                    {/* Meter bar representing consumption of a standard 20 min/month plan limit */}
                    <div className="h-2 bg-zinc-900 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all duration-500 ease-out" 
                        style={{ width: `${Math.min(100, (cogs.compute_stats.gpu_seconds / 1200) * 100)}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-[10px] text-zinc-500 mt-1">
                      <span>0m</span>
                      <span>Plan quota threshold: 20m</span>
                    </div>
                  </div>

                  {/* Profit Margin Match Gauge */}
                  <div>
                    <div className="flex justify-between items-center text-xs text-zinc-400 mb-1.5 font-semibold">
                      <span>Margin Health Target (35% threshold)</span>
                      <span className={`font-bold ${cogs.margin_pct >= 35 ? 'text-green-400' : cogs.margin_pct >= 0 ? 'text-amber-400' : 'text-red-500'}`}>
                        {cogs.margin_pct.toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-zinc-900 rounded-full overflow-hidden">
                        <div 
                          className={`h-full transition-all duration-500 ease-out ${
                            cogs.margin_pct >= 35 
                              ? 'bg-green-500' 
                              : cogs.margin_pct >= 0 
                              ? 'bg-amber-500' 
                              : 'bg-red-500'
                          }`}
                          style={{ width: `${Math.min(100, Math.max(0, cogs.margin_pct))}%` }}
                        />
                      </div>
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase ${
                        cogs.margin_pct >= 35 
                          ? 'bg-green-500/10 text-green-400 border border-green-500/30' 
                          : cogs.margin_pct >= 0 
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30' 
                          : 'bg-red-500/10 text-red-400 border border-red-500/30 animate-pulse'
                      }`}>
                        {cogs.margin_pct >= 35 ? 'Healthy' : cogs.margin_pct >= 0 ? 'Warning' : 'Toxic'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Right Side: Unit Cost Details Matrix */}
                <div className="space-y-3 bg-zinc-900/40 border border-zinc-800/40 rounded-lg p-3">
                  <h4 className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Unit Costs & Ledgers</h4>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between border-b border-zinc-800/60 pb-1.5">
                      <span className="text-zinc-500">Total Infrastructure COGS</span>
                      <span className="text-white font-mono font-bold">€{cogs.total_cogs_eur.toFixed(4)}</span>
                    </div>
                    <div className="flex justify-between text-zinc-400">
                      <span>Replicate GPU Share</span>
                      <span className="font-mono">€{cogs.provider_breakdown.replicate.toFixed(4)}</span>
                    </div>
                    <div className="flex justify-between text-zinc-400">
                      <span>Fly.io Server Processing</span>
                      <span className="font-mono">€{cogs.provider_breakdown.fly_io.toFixed(4)}</span>
                    </div>
                    <div className="flex justify-between text-zinc-400 border-t border-zinc-800/40 pt-1.5">
                      <span>Average Cost / Track</span>
                      <span className="font-mono">€{cogs.cost_per_generation_eur.toFixed(4)}</span>
                    </div>
                  </div>
                </div>

              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
