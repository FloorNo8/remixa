'use client';

import { useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import WaveSurfer from 'wavesurfer.js';

interface WaveformPlayerProps {
  audioUrl: string;
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
      waveformData,
      onPlayStateChange,
      height = 80,
      waveColor = '#4a5568',
      progressColor = '#7c3aed',
    },
    ref
  ) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const wavesurferRef = useRef<WaveSurfer | null>(null);

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
        // Use pre-computed waveform data if available
        wavesurfer.load(audioUrl, [waveformData]);
      } else {
        // Load and compute waveform
        wavesurfer.load(audioUrl);
      }

      // Event listeners
      wavesurfer.on('play', () => {
        onPlayStateChange?.(true);
      });

      wavesurfer.on('pause', () => {
        onPlayStateChange?.(false);
      });

      wavesurfer.on('finish', () => {
        onPlayStateChange?.(false);
      });

      wavesurfer.on('error', (error) => {
        console.error('WaveSurfer error:', error);
      });

      // Cleanup
      return () => {
        wavesurfer.destroy();
      };
    }, [audioUrl, waveformData, height, waveColor, progressColor, onPlayStateChange]);

    return (
      <div className="relative w-full">
        <div ref={containerRef} className="w-full" />
        
        {/* Time display */}
        <div className="flex justify-between text-xs text-gray-400 mt-2">
          <span id="current-time">0:00</span>
          <span id="duration">0:00</span>
        </div>
      </div>
    );
  }
);

WaveformPlayer.displayName = 'WaveformPlayer';

export default WaveformPlayer;
