'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@clerk/nextjs';
import Link from 'next/link';
import { ArrowLeft, Users, Plus, Shield, UserPlus, Info } from 'lucide-react';

interface Member {
  id: string;
  user_id: string;
  username: string;
  share_percentage: number;
}

interface Pool {
  id: string;
  name: string;
  description?: string;
  created_by: string;
  created_at: string;
  is_active: boolean;
  members?: Member[];
}

export default function PoolsPage() {
  const [pools, setPools] = useState<Pool[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newPoolName, setNewPoolName] = useState('');
  const [newPoolDesc, setNewPoolDesc] = useState('');
  const [membersList, setMembersList] = useState<Array<{ user_id: string; share: number }>>([
    { user_id: '', share: 50 },
  ]);
  const [error, setError] = useState<string | null>(null);
  const { getToken } = useAuth();

  useEffect(() => {
    fetchPools();
  }, []);

  const fetchPools = async () => {
    setLoading(true);
    try {
      const token = await getToken();
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBaseUrl}/api/advanced/pools`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) throw new Error('Failed to fetch pools');

      const data = await response.json();
      
      // Fetch members for each pool
      const poolsWithMembers = await Promise.all(
        data.map(async (pool: Pool) => {
          const detailRes = await fetch(`${apiBaseUrl}/api/advanced/pools/${pool.id}`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (detailRes.ok) {
            return await detailRes.json();
          }
          return pool;
        })
      );

      setPools(poolsWithMembers);
    } catch (err: any) {
      console.error('Error fetching pools:', err);
      setError('Could not retrieve collaboration pools.');
    } finally {
      setLoading(false);
    }
  };

  const handleAddMemberInput = () => {
    setMembersList([...membersList, { user_id: '', share: 10 }]);
  };

  const handleMemberChange = (index: number, key: 'user_id' | 'share', value: string | number) => {
    const updated = [...membersList];
    if (key === 'user_id') {
      updated[index].user_id = value as string;
    } else {
      updated[index].share = value as number;
    }
    setMembersList(updated);
  };

  const handleRemoveMemberInput = (index: number) => {
    setMembersList(membersList.filter((_, i) => i !== index));
  };

  const handleCreatePool = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const totalShare = membersList.reduce((acc, m) => acc + m.share, 0);
    if (totalShare > 100) {
      setError('Total member shares cannot exceed 100%.');
      return;
    }

    try {
      const token = await getToken();
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      
      // 1. Create the pool
      const poolResponse = await fetch(`${apiBaseUrl}/api/advanced/pools`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: newPoolName,
          description: newPoolDesc,
        }),
      });

      if (!poolResponse.ok) {
        const errData = await poolResponse.json();
        throw new Error(errData.detail || 'Failed to create pool');
      }

      const poolData = await poolResponse.json();
      const poolId = poolData.id;

      // 2. Add members
      for (const member of membersList) {
        if (!member.user_id.trim()) continue;

        const memberRes = await fetch(`${apiBaseUrl}/api/advanced/royalties/pools/${poolId}/members`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            user_id: member.user_id,
            share_percentage: member.share,
          }),
        });

        if (!memberRes.ok) {
          const memberErr = await memberRes.json();
          throw new Error(`Failed to add member ${member.user_id}: ${memberErr.detail || 'Error'}`);
        }
      }

      setShowCreateModal(false);
      setNewPoolName('');
      setNewPoolDesc('');
      setMembersList([{ user_id: '', share: 50 }]);
      fetchPools();
    } catch (err: any) {
      console.error('Error creating pool:', err);
      setError(err.message || 'An error occurred during pool creation.');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#7c3aed]"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#1a1a1a] border-b border-gray-800">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <Link href="/dashboard" className="flex items-center space-x-2 text-gray-400 hover:text-white">
              <ArrowLeft className="w-5 h-5" />
              <span>Dashboard</span>
            </Link>
            <div className="flex items-center space-x-2">
              <Users className="w-8 h-8 text-[#7c3aed]" />
              <span className="text-2xl font-bold">Collaboration Pools</span>
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex items-center space-x-1 px-4 py-2 bg-[#7c3aed] text-white rounded-lg hover:bg-[#6d28d9] transition-colors text-sm font-medium"
            >
              <Plus className="w-4 h-4" />
              <span>Create Pool</span>
            </button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 max-w-4xl">
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg text-sm flex items-start space-x-2">
            <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="space-y-6">
          {pools.length === 0 ? (
            <div className="bg-[#1a1a1a] border border-gray-800 rounded-lg p-12 text-center">
              <Users className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <h3 className="text-xl font-bold text-white mb-2">No Collaboration Pools</h3>
              <p className="text-gray-400 mb-6 max-w-md mx-auto">
                Collaboration pools allow groups of creators to distribute remix royalties automatically. Create your first pool to get started.
              </p>
              <button
                onClick={() => setShowCreateModal(true)}
                className="px-6 py-2.5 bg-[#7c3aed] text-white rounded-lg hover:bg-[#6d28d9] transition-colors text-sm font-medium"
              >
                Create Collaboration Pool
              </button>
            </div>
          ) : (
            pools.map((pool) => (
              <div key={pool.id} className="bg-[#1a1a1a] border border-gray-800 rounded-lg p-6">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-xl font-bold text-white mb-1">{pool.name}</h3>
                    <p className="text-gray-400 text-sm">{pool.description || 'No description provided'}</p>
                  </div>
                  <span className="flex items-center px-2 py-0.5 text-xs font-semibold rounded-full bg-green-500/10 text-green-400 border border-green-500/30">
                    <Shield className="w-3.5 h-3.5 mr-1" /> Active
                  </span>
                </div>

                <div className="border-t border-gray-800 pt-4 mt-4">
                  <h4 className="text-sm font-semibold text-gray-400 mb-3">Members & Split Allocation</h4>
                  <div className="space-y-3">
                    {pool.members && pool.members.length > 0 ? (
                      pool.members.map((member) => (
                        <div key={member.id} className="flex justify-between items-center bg-[#0a0a0a] px-4 py-2.5 rounded-lg border border-gray-800/50">
                          <span className="text-sm text-gray-300 font-medium">
                            @{member.username} <span className="text-xs text-gray-600">({member.user_id})</span>
                          </span>
                          <span className="text-sm text-white font-bold bg-[#1a1a1a] px-2.5 py-1 rounded">
                            {member.share_percentage}%
                          </span>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-gray-500">No members configured in this pool yet.</p>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </main>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#1a1a1a] rounded-lg max-w-lg w-full p-6 border border-gray-800">
            <h3 className="text-xl font-bold text-white mb-4">Create Collaboration Pool</h3>
            <form onSubmit={handleCreatePool} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Pool Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Summer Remix Collab"
                  value={newPoolName}
                  onChange={(e) => setNewPoolName(e.target.value)}
                  className="w-full bg-[#0a0a0a] text-white rounded-lg p-3 border border-gray-800 focus:border-[#7c3aed] focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Description</label>
                <textarea
                  placeholder="Describe the collaboration context..."
                  value={newPoolDesc}
                  onChange={(e) => setNewPoolDesc(e.target.value)}
                  className="w-full h-20 bg-[#0a0a0a] text-white rounded-lg p-3 border border-gray-800 focus:border-[#7c3aed] focus:outline-none resize-none"
                />
              </div>

              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider">Members & Splits</label>
                  <button
                    type="button"
                    onClick={handleAddMemberInput}
                    className="flex items-center space-x-1 text-xs text-[#7c3aed] hover:text-[#6d28d9] font-medium"
                  >
                    <UserPlus className="w-3.5 h-3.5" />
                    <span>Add Member</span>
                  </button>
                </div>

                <div className="space-y-3 max-h-48 overflow-y-auto pr-1">
                  {membersList.map((member, index) => (
                    <div key={index} className="flex space-x-2 items-center">
                      <input
                        type="text"
                        required
                        placeholder="User UUID"
                        value={member.user_id}
                        onChange={(e) => handleMemberChange(index, 'user_id', e.target.value)}
                        className="flex-1 bg-[#0a0a0a] text-white rounded-lg p-2.5 border border-gray-800 text-sm focus:outline-none"
                      />
                      <div className="flex items-center space-x-1 bg-[#0a0a0a] border border-gray-800 rounded-lg p-2.5">
                        <input
                          type="number"
                          required
                          min="1"
                          max="100"
                          value={member.share}
                          onChange={(e) => handleMemberChange(index, 'share', parseInt(e.target.value))}
                          className="w-12 bg-transparent text-white text-center text-sm focus:outline-none font-medium"
                        />
                        <span className="text-gray-500 text-sm">%</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoveMemberInput(index)}
                        className="p-2 text-gray-500 hover:text-red-500 rounded"
                        disabled={membersList.length === 1}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex space-x-3 pt-4">
                <button
                  type="submit"
                  className="flex-1 py-3 bg-[#7c3aed] text-white rounded-lg font-bold hover:bg-[#6d28d9] transition-colors"
                >
                  Create Pool
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 py-3 bg-[#2a2a2a] text-white rounded-lg font-bold hover:bg-[#333] transition-colors"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
