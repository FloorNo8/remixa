import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

interface Tape {
  id: string;
  prompt: string;
  audio_url: string;
  waveform_data?: number[];
  creator: {
    id: string;
    username: string;
    avatar_url?: string;
  };
  remix_count: number;
  total_earnings: number;
  likes_count: number;
  is_liked: boolean;
  created_at: string;
  has_c2pa: boolean;
  parent_id?: string;
}

type SortOption = 'trending' | 'new' | 'following' | 'top-earners';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function useTapes(sortBy: SortOption = 'trending') {
  const [tapes, setTapes] = useState<Tape[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const fetchTapes = useCallback(async (pageNum: number, reset: boolean = false) => {
    if (loading) return;
    
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(`${API_BASE_URL}/api/explore`, {
        params: {
          sort: sortBy,
          page: pageNum,
          limit: 12,
        },
        headers: {
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });

      const newTapes = response.data.tapes || [];
      
      if (reset) {
        setTapes(newTapes);
      } else {
        setTapes(prev => [...prev, ...newTapes]);
      }

      setHasMore(newTapes.length === 12);
      setPage(pageNum);
    } catch (err: any) {
      console.error('Failed to fetch tapes:', err);
      setError(err.response?.data?.detail || 'Failed to load tapes');
    } finally {
      setLoading(false);
    }
  }, [sortBy, loading]);

  // Reset and fetch when sortBy changes
  useEffect(() => {
    setTapes([]);
    setPage(1);
    setHasMore(true);
    fetchTapes(1, true);
  }, [sortBy]);

  const loadMore = useCallback(() => {
    if (hasMore && !loading) {
      fetchTapes(page + 1, false);
    }
  }, [hasMore, loading, page, fetchTapes]);

  return {
    tapes,
    loading,
    hasMore,
    loadMore,
    error,
  };
}
