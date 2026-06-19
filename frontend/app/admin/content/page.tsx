'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@clerk/nextjs';

interface Content {
  id: string;
  prompt: string;
  audio_url: string;
  layer_type: string;
  created_at: string;
  status: string;
  featured: boolean;
  plays: number;
  likes: number;
  creator_email: string;
  creator_username: string;
  remix_count: number;
}

export default function ContentManagement() {
  const [content, setContent] = useState<Content[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const { getToken } = useAuth();

  const ITEMS_PER_PAGE = 20;

  useEffect(() => {
    fetchContent();
  }, [page]);

  async function fetchContent() {
    setLoading(true);
    try {
      const token = await getToken();
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/admin/content?limit=${ITEMS_PER_PAGE}&offset=${page * ITEMS_PER_PAGE}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) throw new Error('Failed to fetch content');

      const data = await response.json();
      setContent(data);
    } catch (error) {
      console.error('Error fetching content:', error);
    } finally {
      setLoading(false);
    }
  }

  async function handleFeature(generationId: string, featured: boolean) {
    try {
      const token = await getToken();
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/admin/content/${generationId}/feature`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ featured }),
        }
      );

      if (!response.ok) throw new Error('Failed to feature content');

      fetchContent();
    } catch (error) {
      console.error('Error featuring content:', error);
      alert('Failed to feature content');
    }
  }

  async function handleDelete(generationId: string, reason: string) {
    try {
      const token = await getToken();
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/admin/content/${generationId}?reason=${encodeURIComponent(reason)}`,
        {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) throw new Error('Failed to delete content');

      fetchContent();
    } catch (error) {
      console.error('Error deleting content:', error);
      alert('Failed to delete content');
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Content Management</h1>
        <p className="text-zinc-400">Browse and manage all platform content</p>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <div className="text-zinc-400">
          Showing {page * ITEMS_PER_PAGE + 1} -{' '}
          {Math.min((page + 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE + content.length)}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setPage(Math.max(0, page - 1))}
            disabled={page === 0}
            className="px-4 py-2 bg-zinc-800 text-white rounded-lg hover:bg-zinc-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            ← Previous
          </button>
          <button
            onClick={() => setPage(page + 1)}
            disabled={content.length < ITEMS_PER_PAGE}
            className="px-4 py-2 bg-zinc-800 text-white rounded-lg hover:bg-zinc-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next →
          </button>
        </div>
      </div>

      {/* Content List */}
      {loading ? (
        <div className="text-center py-12 text-zinc-400">Loading content...</div>
      ) : content.length === 0 ? (
        <div className="text-center py-12 text-zinc-400">No content found</div>
      ) : (
        <div className="space-y-4">
          {content.map((item) => (
            <ContentCard
              key={item.id}
              content={item}
              onFeature={handleFeature}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ContentCard({
  content,
  onFeature,
  onDelete,
}: {
  content: Content;
  onFeature: (id: string, featured: boolean) => void;
  onDelete: (id: string, reason: string) => void;
}) {
  const [showDeleteInput, setShowDeleteInput] = useState(false);
  const [deleteReason, setDeleteReason] = useState('');

  return (
    <div className="bg-zinc-900 rounded-lg p-6 border border-zinc-800">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Content Info */}
        <div className="md:col-span-2 space-y-3">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                {content.featured && (
                  <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 text-xs rounded">
                    ⭐ Featured
                  </span>
                )}
                <span className="px-2 py-1 bg-zinc-800 text-zinc-300 text-xs rounded">
                  {content.layer_type}
                </span>
              </div>
              <div className="text-white font-medium mb-1">{content.prompt}</div>
              <div className="text-sm text-zinc-400">
                by {content.creator_username} ({content.creator_email})
              </div>
            </div>
          </div>

          {content.audio_url && (
            <audio controls className="w-full">
              <source src={content.audio_url} type="audio/mpeg" />
            </audio>
          )}

          <div className="flex gap-4 text-sm">
            <div className="text-zinc-400">
              <span className="text-white">{content.plays}</span> plays
            </div>
            <div className="text-zinc-400">
              <span className="text-white">{content.likes}</span> likes
            </div>
            <div className="text-zinc-400">
              <span className="text-white">{content.remix_count}</span> remixes
            </div>
          </div>

          <div className="text-xs text-zinc-500">
            Created {new Date(content.created_at).toLocaleString()}
          </div>
        </div>

        {/* Actions */}
        <div className="space-y-2">
          <button
            onClick={() => onFeature(content.id, !content.featured)}
            className={`w-full px-4 py-2 rounded-lg transition-colors ${
              content.featured
                ? 'bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30 border border-yellow-500/50'
                : 'bg-zinc-800 text-white hover:bg-zinc-700'
            }`}
          >
            {content.featured ? '⭐ Unfeature' : '⭐ Feature'}
          </button>

          <a
            href={`/tape/${content.id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="block w-full px-4 py-2 bg-zinc-800 text-white text-center rounded-lg hover:bg-zinc-700 transition-colors"
          >
            View Tape →
          </a>

          {showDeleteInput ? (
            <div className="space-y-2">
              <input
                type="text"
                placeholder="Reason for deletion..."
                value={deleteReason}
                onChange={(e) => setDeleteReason(e.target.value)}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded text-white text-sm placeholder-zinc-500 focus:outline-none focus:border-zinc-600"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    if (deleteReason.trim()) {
                      if (confirm('Delete this content permanently?')) {
                        onDelete(content.id, deleteReason);
                        setDeleteReason('');
                        setShowDeleteInput(false);
                      }
                    }
                  }}
                  disabled={!deleteReason.trim()}
                  className="flex-1 px-3 py-2 bg-red-500 text-white rounded text-sm hover:bg-red-600 transition-colors disabled:opacity-50"
                >
                  Confirm
                </button>
                <button
                  onClick={() => {
                    setDeleteReason('');
                    setShowDeleteInput(false);
                  }}
                  className="px-3 py-2 bg-zinc-800 text-white rounded text-sm hover:bg-zinc-700 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowDeleteInput(true)}
              className="w-full px-4 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors border border-red-500/50"
            >
              🗑️ Delete
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
