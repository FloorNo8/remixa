'use client';

import { useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { useAuth } from '@clerk/nextjs';

interface WaveformPlayerProps {
  audioUrl: string;
  generationId?: string;
  waveformData?: number[];
  onPlayStateChange?: (isPlaying: boolean) => void;
  height?: number;
  waveColor?: string;
  progressColor?: string;
}

export interface WaveformPlayerHandle {
  play: () => void;
  pause: () => void;
  stop: () => void;
  getCurrentTime: () => number;
  getDuration: () => number;
  getAudioElement: () => HTMLAudioElement | null;
}

const WaveformPlayer = forwardRef<WaveformPlayerHandle, WaveformPlayerProps>(
  (
    {
      audioUrl,
      generationId,
      waveformData,
      onPlayStateChange,
      height = 80,
      waveColor = '#4a5568',
      progressColor = '#7c3aed',
    },
    ref
  ) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const currentTimeRef = useRef<HTMLSpanElement>(null);
    const durationRef = useRef<HTMLSpanElement>(null);
    const wavesurferRef = useRef<WaveSurfer | null>(null);
    const { getToken } = useAuth();
    const lastPlaybackState = useRef({ currentTime: 0, wasPlaying: false, audioUrl: '' });

    useImperativeHandle(ref, () => ({
      play: () => wavesurferRef.current?.play(),
      pause: () => wavesurferRef.current?.pause(),
      stop: () => wavesurferRef.current?.stop(),
      getCurrentTime: () => wavesurferRef.current?.getCurrentTime() || 0,
      getDuration: () => wavesurferRef.current?.getDuration() || 0,
      getAudioElement: () => {
        const backend = wavesurferRef.current?.getMediaElement();
        return backend instanceof HTMLAudioElement ? backend : null;
      },
    }));

    useEffect(() => {
      if (!containerRef.current) return;

      // Save state from previous wavesurfer if url changed
      if (wavesurferRef.current && lastPlaybackState.current.audioUrl !== audioUrl) {
        lastPlaybackState.current = {
          currentTime: wavesurferRef.current.getCurrentTime(),
          wasPlaying: wavesurferRef.current.isPlaying(),
          audioUrl: audioUrl
        };
      } else if (!wavesurferRef.current) {
        lastPlaybackState.current.audioUrl = audioUrl;
      }

      // Initialize WaveSurfer
      const wavesurfer = WaveSurfer.create({
        container: containerRef.current,
        waveColor,
        progressColor,
        cursorColor: progressColor,
        barWidth: 2,
        barRadius: 3,
        cursorWidth: 1,
        height,
        barGap: 2,
        normalize: true,
        backend: 'WebAudio',
      });

      wavesurferRef.current = wavesurfer;

      // Load audio
      if (waveformData && waveformData.length > 0) {
        wavesurfer.load(audioUrl, [waveformData]);
      } else {
        wavesurfer.load(audioUrl);
      }

      // Track logged milestones
      const loggedMilestones = {
        play_10s: false,
        play_50s: false,
        play_100s: false,
      };

      const formatTime = (time: number) => {
        const minutes = Math.floor(time / 60);
        const seconds = Math.floor(time % 60);
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
      };

      // Event listeners
      wavesurfer.on('ready', () => {
        if (durationRef.current) {
          durationRef.current.textContent = formatTime(wavesurfer.getDuration());
        }
        
        // Restore playback position and play state if switching streams of same track
        if (lastPlaybackState.current.currentTime > 0) {
          wavesurfer.setTime(lastPlaybackState.current.currentTime);
          if (lastPlaybackState.current.wasPlaying) {
            wavesurfer.play();
          }
          lastPlaybackState.current.currentTime = 0;
        }
      });

      wavesurfer.on('play', () => {
        onPlayStateChange?.(true);
      });

      wavesurfer.on('pause', () => {
        onPlayStateChange?.(false);
      });

      wavesurfer.on('audioprocess', async () => {
        if (currentTimeRef.current) {
          currentTimeRef.current.textContent = formatTime(wavesurfer.getCurrentTime());
        }

        if (!generationId) return;
        const duration = wavesurfer.getDuration();
        const currentTime = wavesurfer.getCurrentTime();
        if (duration <= 0) return;

        const ratio = currentTime / duration;
        let action: 'play_10s' | 'play_50s' | 'play_100s' | null = null;

        if (ratio >= 0.1 && !loggedMilestones.play_10s) {
          loggedMilestones.play_10s = true;
          action = 'play_10s';
        }
        if (ratio >= 0.5 && !loggedMilestones.play_50s) {
          loggedMilestones.play_50s = true;
          action = 'play_50s';
        }
        if (ratio >= 0.98 && !loggedMilestones.play_100s) {
          loggedMilestones.play_100s = true;
          action = 'play_100s';
        }

        if (action) {
          try {
            const token = await getToken();
            const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || '';
            await fetch(`${apiBaseUrl}/api/v2/metrics`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                ...(token && { Authorization: `Bearer ${token}` }),
              },
              body: JSON.stringify({
                generation_id: generationId,
                action,
              }),
            });
          } catch (err) {
            console.error('Failed to log playback metric:', err);
          }
        }
      });

      wavesurfer.on('finish', async () => {
        onPlayStateChange?.(false);
        if (generationId && !loggedMilestones.play_100s) {
          loggedMilestones.play_100s = true;
          try {
            const token = await getToken();
            const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || '';
            await fetch(`${apiBaseUrl}/api/v2/metrics`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                ...(token && { Authorization: `Bearer ${token}` }),
              },
              body: JSON.stringify({
                generation_id: generationId,
                action: 'play_100s',
              }),
            });
          } catch (err) {
            console.error('Failed to log finish metric:', err);
          }
        }
      });

      wavesurfer.on('error', (error) => {
        console.error('WaveSurfer error:', error);
      });

      // Cleanup
      return () => {
        wavesurfer.destroy();
      };
    }, [audioUrl, generationId, waveformData, height, waveColor, progressColor, onPlayStateChange, getToken]);

    return (
      <div className="relative w-full">
        <div ref={containerRef} className="w-full" />
        
        {/* Time display */}
        <div className="flex justify-between text-xs text-gray-400 mt-2">
          <span ref={currentTimeRef}>0:00</span>
          <span ref={durationRef}>0:00</span>
        </div>
      </div>
    );
  }
);

WaveformPlayer.displayName = 'WaveformPlayer';

export default WaveformPlayer;
