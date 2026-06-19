'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@clerk/nextjs';

interface Metrics {
  users: {
    total: number;
    new_today: number;
    active_7d: number;
  };
  generations: {
    total: number;
    today: number;
    success_rate: number;
  };
  revenue: {
    total: number;
    today: number;
    pending_payouts: number;
  };
  moderation: {
    pending_reports: number;
    resolved_today: number;
  };
}

export default function AdminDashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const { getToken } = useAuth();

  useEffect(() => {
    async function fetchMetrics() {
      try {
        const token = await getToken();
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/api/admin/dashboard`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error('Failed to fetch metrics');
        }

        const data = await response.json();
        setMetrics(data);
      } catch (error) {
        console.error('Error fetching metrics:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchMetrics();
  }, [getToken]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-zinc-400">Loading metrics...</div>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-400">Failed to load metrics</div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
        <p className="text-zinc-400">Overview of platform metrics and activity</p>
      </div>

      {/* User Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          title="Total Users"
          value={metrics.users.total.toLocaleString()}
          change={`+${metrics.users.new_today} today`}
          changeType="positive"
        />
        <MetricCard
          title="Active Users (7d)"
          value={metrics.users.active_7d.toLocaleString()}
          subtitle="Unique users with generations"
        />
        <MetricCard
          title="New Today"
          value={metrics.users.new_today.toLocaleString()}
          subtitle="User registrations"
        />
      </div>

      {/* Generation Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          title="Total Generations"
          value={metrics.generations.total.toLocaleString()}
          change={`+${metrics.generations.today} today`}
          changeType="positive"
        />
        <MetricCard
          title="Today's Generations"
          value={metrics.generations.today.toLocaleString()}
        />
        <MetricCard
          title="Success Rate (7d)"
          value={`${(metrics.generations.success_rate * 100).toFixed(1)}%`}
          changeType={metrics.generations.success_rate > 0.95 ? 'positive' : 'neutral'}
        />
      </div>

      {/* Revenue & Moderation */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-zinc-900 rounded-lg p-6 border border-zinc-800">
          <h2 className="text-xl font-bold text-white mb-4">💰 Revenue</h2>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-zinc-400">Total Revenue</span>
              <span className="text-white font-mono text-lg">
                €{metrics.revenue.total.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-zinc-400">Today</span>
              <span className="text-green-400 font-mono">
                €{metrics.revenue.today.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between items-center pt-3 border-t border-zinc-800">
              <span className="text-zinc-400">Pending Payouts</span>
              <span className="text-yellow-400 font-mono">
                €{metrics.revenue.pending_payouts.toFixed(2)}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-zinc-900 rounded-lg p-6 border border-zinc-800">
          <h2 className="text-xl font-bold text-white mb-4">🛡️ Moderation</h2>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-zinc-400">Pending Reports</span>
              <span
                className={`font-mono text-lg ${
                  metrics.moderation.pending_reports > 0
                    ? 'text-red-400'
                    : 'text-green-400'
                }`}
              >
                {metrics.moderation.pending_reports}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-zinc-400">Resolved Today</span>
              <span className="text-white font-mono">
                {metrics.moderation.resolved_today}
              </span>
            </div>
            {metrics.moderation.pending_reports > 0 && (
              <a
                href="/admin/moderation"
                className="block mt-4 text-center py-2 px-4 bg-red-500/10 text-red-400 rounded-lg hover:bg-red-500/20 transition-colors"
              >
                Review Queue →
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-zinc-900 rounded-lg p-6 border border-zinc-800">
        <h2 className="text-xl font-bold text-white mb-4">⚡ Quick Actions</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <QuickActionButton href="/admin/moderation" label="Moderation Queue" />
          <QuickActionButton href="/admin/users" label="Search Users" />
          <QuickActionButton href="/admin/content" label="Browse Content" />
          <QuickActionButton href="/admin/vat" label="VAT Reports" />
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  title,
  value,
  subtitle,
  change,
  changeType = 'neutral',
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  change?: string;
  changeType?: 'positive' | 'negative' | 'neutral';
}) {
  const changeColors = {
    positive: 'text-green-400',
    negative: 'text-red-400',
    neutral: 'text-zinc-400',
  };

  return (
    <div className="bg-zinc-900 rounded-lg p-6 border border-zinc-800">
      <div className="text-zinc-400 text-sm mb-2">{title}</div>
      <div className="text-3xl font-bold text-white mb-1">{value}</div>
      {change && (
        <div className={`text-sm ${changeColors[changeType]}`}>{change}</div>
      )}
      {subtitle && <div className="text-sm text-zinc-500 mt-1">{subtitle}</div>}
    </div>
  );
}

function QuickActionButton({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      className="block py-3 px-4 bg-zinc-800 hover:bg-zinc-700 text-white text-center rounded-lg transition-colors"
    >
      {label}
    </a>
  );
}
