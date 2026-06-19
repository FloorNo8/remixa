'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@clerk/nextjs';

interface Report {
  id: string;
  generation_id: string;
  reason: string;
  status: string;
  created_at: string;
  prompt: string;
  audio_url: string;
  layer_type: string;
  reporter_email: string;
  reporter_username: string;
  creator_username: string;
}

export default function ModerationQueue() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<'pending' | 'approved' | 'rejected'>('pending');
  const { getToken } = useAuth();

  useEffect(() => {
    fetchReports();
  }, [status]);

  async function fetchReports() {
    setLoading(true);
    try {
      const token = await getToken();
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/admin/moderation/queue?status=${status}&limit=50`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) throw new Error('Failed to fetch reports');

      const data = await response.json();
      setReports(data);
    } catch (error) {
      console.error('Error fetching reports:', error);
    } finally {
      setLoading(false);
    }
  }

  async function handleAction(reportId: string, action: string, reason?: string) {
    try {
      const token = await getToken();
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/admin/moderation/${reportId}/action?action=${action}`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ reason }),
        }
      );

      if (!response.ok) throw new Error('Failed to take action');

      // Refresh the list
      fetchReports();
    } catch (error) {
      console.error('Error taking action:', error);
      alert('Failed to take action');
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Moderation Queue</h1>
        <p className="text-zinc-400">Review and take action on reported content</p>
      </div>

      {/* Status Filter */}
      <div className="flex gap-2">
        <button
          onClick={() => setStatus('pending')}
          className={`px-4 py-2 rounded-lg transition-colors ${
            status === 'pending'
              ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/50'
              : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
          }`}
        >
          Pending
        </button>
        <button
          onClick={() => setStatus('approved')}
          className={`px-4 py-2 rounded-lg transition-colors ${
            status === 'approved'
              ? 'bg-green-500/20 text-green-400 border border-green-500/50'
              : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
          }`}
        >
          Approved
        </button>
        <button
          onClick={() => setStatus('rejected')}
          className={`px-4 py-2 rounded-lg transition-colors ${
            status === 'rejected'
              ? 'bg-red-500/20 text-red-400 border border-red-500/50'
              : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
          }`}
        >
          Rejected
        </button>
      </div>

      {/* Reports List */}
      {loading ? (
        <div className="text-center py-12 text-zinc-400">Loading reports...</div>
      ) : reports.length === 0 ? (
        <div className="text-center py-12 text-zinc-400">
          No {status} reports found
        </div>
      ) : (
        <div className="space-y-4">
          {reports.map((report) => (
            <ReportCard
              key={report.id}
              report={report}
              onAction={handleAction}
              showActions={status === 'pending'}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ReportCard({
  report,
  onAction,
  showActions,
}: {
  report: Report;
  onAction: (reportId: string, action: string, reason?: string) => void;
  showActions: boolean;
}) {
  const [actionReason, setActionReason] = useState('');
  const [showReasonInput, setShowReasonInput] = useState(false);

  return (
    <div className="bg-zinc-900 rounded-lg p-6 border border-zinc-800">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Report Info */}
        <div className="space-y-3">
          <div>
            <div className="text-sm text-zinc-400 mb-1">Reported by</div>
            <div className="text-white">
              {report.reporter_username} ({report.reporter_email})
            </div>
          </div>

          <div>
            <div className="text-sm text-zinc-400 mb-1">Reason</div>
            <div className="text-white">{report.reason}</div>
          </div>

          <div>
            <div className="text-sm text-zinc-400 mb-1">Reported at</div>
            <div className="text-white">
              {new Date(report.created_at).toLocaleString()}
            </div>
          </div>
        </div>

        {/* Content Info */}
        <div className="space-y-3">
          <div>
            <div className="text-sm text-zinc-400 mb-1">Creator</div>
            <div className="text-white">{report.creator_username}</div>
          </div>

          <div>
            <div className="text-sm text-zinc-400 mb-1">Prompt</div>
            <div className="text-white text-sm">{report.prompt}</div>
          </div>

          <div>
            <div className="text-sm text-zinc-400 mb-1">Layer Type</div>
            <div className="text-white">{report.layer_type}</div>
          </div>

          {report.audio_url && (
            <div>
              <audio controls className="w-full">
                <source src={report.audio_url} type="audio/mpeg" />
              </audio>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      {showActions && (
        <div className="mt-6 pt-6 border-t border-zinc-800">
          {showReasonInput ? (
            <div className="space-y-3">
              <input
                type="text"
                placeholder="Enter reason for action..."
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
                className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => setShowReasonInput(false)}
                  className="px-4 py-2 bg-zinc-800 text-white rounded-lg hover:bg-zinc-700 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <button
                onClick={() => {
                  if (confirm('Delete this content?')) {
                    onAction(report.id, 'delete_content', 'Content deleted by moderator');
                  }
                }}
                className="px-4 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors border border-red-500/50"
              >
                🗑️ Delete Content
              </button>
              <button
                onClick={() => {
                  setShowReasonInput(true);
                  setActionReason('Report approved - content removed');
                }}
                className="px-4 py-2 bg-green-500/20 text-green-400 rounded-lg hover:bg-green-500/30 transition-colors border border-green-500/50"
              >
                ✓ Approve Report
              </button>
              <button
                onClick={() => {
                  setShowReasonInput(true);
                  setActionReason('Report rejected - no violation found');
                }}
                className="px-4 py-2 bg-zinc-800 text-white rounded-lg hover:bg-zinc-700 transition-colors"
              >
                ✗ Reject Report
              </button>
            </div>
          )}

          {showReasonInput && actionReason && (
            <div className="flex gap-2 mt-3">
              <button
                onClick={() => {
                  const action = actionReason.includes('approved') ? 'approve' : 'reject';
                  onAction(report.id, action, actionReason);
                  setShowReasonInput(false);
                  setActionReason('');
                }}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
              >
                Confirm Action
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
