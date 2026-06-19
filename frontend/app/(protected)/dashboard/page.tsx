'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { Music, TrendingUp, Clock, Users, Plus } from 'lucide-react';
import Link from 'next/link';
import TapeCard from '@/components/TapeCard';
import { FeedSkeleton } from '@/components/LoadingSkeleton';
import { ErrorDisplay } from '@/components/ErrorBoundary';
import { fetcher } from '@/lib/fetcher';

type SortOption = 'trending' | 'new' | 'following' | 'top-earners';

export default function DashboardPage() {
  const [sortBy, setSortBy] = useState<SortOption>('trending');
  
  const { data, error, isLoading, mutate } = useSWR(
    `/api/explore?sort=${sortBy}`,
    fetcher,
    {
      refreshInterval: 30000,
      revalidateOnFocus: true,
      dedupingInterval: 10000,
    }
  );

  const tapes = data?.tapes || [];
  const loading = isLoading;

  const handleRefresh = () => mutate();

  return (
    <div className="min-h-screen bg-[#0a0a0a]">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#1a1a1a] border-b border-gray-800">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Music className="w-8 h-8 text-[#7c3aed]" />
              <span className="text-2xl font-bold text-white">EU Sound Lab</span>
            </div>
            
            <nav className="hidden md:flex items-center space-x-6">
              <Link href="/dashboard" className="text-white font-medium">
                Explore
              </Link>
              <Link href="/earnings" className="text-gray-400 hover:text-white">
                Earnings
              </Link>
              <Link href="/profile" className="text-gray-400 hover:text-white">
                Profile
              </Link>
            </nav>

            <div className="flex items-center space-x-4">
              <button className="text-gray-400 hover:text-white">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
              </button>
              <div className="w-10 h-10 rounded-full bg-[#7c3aed] flex items-center justify-center text-white font-bold">
                ST
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Filter Tabs */}
      <div className="container mx-auto px-4 py-6">
        <div className="flex space-x-2 overflow-x-auto pb-2">
          <button
            onClick={() => setSortBy('trending')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg whitespace-nowrap transition-colors ${
              sortBy === 'trending'
                ? 'bg-[#7c3aed] text-white'
                : 'bg-[#1a1a1a] text-gray-400 hover:text-white'
            }`}
          >
            <TrendingUp className="w-4 h-4" />
            <span>Trending</span>
          </button>
          
          <button
            onClick={() => setSortBy('new')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg whitespace-nowrap transition-colors ${
              sortBy === 'new'
                ? 'bg-[#7c3aed] text-white'
                : 'bg-[#1a1a1a] text-gray-400 hover:text-white'
            }`}
          >
            <Clock className="w-4 h-4" />
            <span>New</span>
          </button>
          
          <button
            onClick={() => setSortBy('following')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg whitespace-nowrap transition-colors ${
              sortBy === 'following'
                ? 'bg-[#7c3aed] text-white'
                : 'bg-[#1a1a1a] text-gray-400 hover:text-white'
            }`}
          >
            <Users className="w-4 h-4" />
            <span>Following</span>
          </button>
          
          <button
            onClick={() => setSortBy('top-earners')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg whitespace-nowrap transition-colors ${
              sortBy === 'top-earners'
                ? 'bg-[#7c3aed] text-white'
                : 'bg-[#1a1a1a] text-gray-400 hover:text-white'
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>Top Earners</span>
          </button>
        </div>
      </div>

      {/* Tape Grid */}
      <div className="container mx-auto px-4 pb-20">
        {loading && tapes.length === 0 ? (
          <FeedSkeleton />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {tapes.map((tape: any) => (
              <TapeCard key={tape.id} tape={tape} />
            ))}
          </div>
        )}

        {loading && tapes.length > 0 && (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#7c3aed]"></div>
          </div>
        )}

        {!loading && tapes.length === 0 && (
          <div className="text-center py-20">
            {sortBy === 'following' ? (
              <>
                <Users className="w-16 h-16 text-gray-600 mx-auto mb-4" />
                <h3 className="text-xl font-bold text-white mb-2">No tapes from followed creators</h3>
                <p className="text-gray-400 mb-6">
                  Follow creators to see their latest tapes here
                </p>
                <Link
                  href="/dashboard?sort=trending"
                  className="inline-flex items-center space-x-2 px-6 py-3 bg-[#7c3aed] text-white rounded-lg hover:bg-[#6d28d9] transition-colors"
                >
                  <TrendingUp className="w-5 h-5" />
                  <span>Explore Trending</span>
                </Link>
              </>
            ) : (
              <>
                <Music className="w-16 h-16 text-gray-600 mx-auto mb-4" />
                <h3 className="text-xl font-bold text-white mb-2">No tapes yet</h3>
                <p className="text-gray-400 mb-6">Be the first to create something amazing!</p>
                <Link
                  href="/create"
                  className="inline-flex items-center space-x-2 px-6 py-3 bg-[#7c3aed] text-white rounded-lg hover:bg-[#6d28d9] transition-colors"
                >
                  <Plus className="w-5 h-5" />
                  <span>Create Tape</span>
                </Link>
              </>
            )}
          </div>
        )}
      </div>

      {/* Create FAB */}
      <Link
        href="/create"
        className="fixed bottom-6 right-6 w-16 h-16 bg-[#7c3aed] rounded-full flex items-center justify-center shadow-lg hover:bg-[#6d28d9] transition-colors z-40"
      >
        <Plus className="w-8 h-8 text-white" />
      </Link>

      {/* Mobile Bottom Nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-[#1a1a1a] border-t border-gray-800 z-50">
        <div className="flex justify-around py-3">
          <Link href="/dashboard" className="flex flex-col items-center text-[#7c3aed]">
            <Music className="w-6 h-6" />
            <span className="text-xs mt-1">Explore</span>
          </Link>
          <Link href="/create" className="flex flex-col items-center text-gray-400">
            <Plus className="w-6 h-6" />
            <span className="text-xs mt-1">Create</span>
          </Link>
          <Link href="/earnings" className="flex flex-col items-center text-gray-400">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-xs mt-1">Earnings</span>
          </Link>
          <Link href="/profile" className="flex flex-col items-center text-gray-400">
            <Users className="w-6 h-6" />
            <span className="text-xs mt-1">Profile</span>
          </Link>
        </div>
      </nav>
    </div>
  );
}
