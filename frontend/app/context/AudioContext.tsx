'use client';

import { createContext, useContext, useState, useRef, ReactNode } from 'react';

interface AudioContextType {
  currentPlaying: string | null;
  play: (id: string, audioElement: HTMLAudioElement) => void;
  pause: (id: string) => void;
  isPlaying: (id: string) => boolean;
}

const AudioContext = createContext<AudioContextType | undefined>(undefined);

export function AudioProvider({ children }: { children: ReactNode }) {
  const [currentPlaying, setCurrentPlaying] = useState<string | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  const play = (id: string, audioElement: HTMLAudioElement) => {
    // Pause currently playing audio if different
    if (currentAudioRef.current && currentPlaying !== id) {
      currentAudioRef.current.pause();
      currentAudioRef.current.currentTime = 0;
    }

    // Update state
    setCurrentPlaying(id);
    currentAudioRef.current = audioElement;

    // Play new audio
    audioElement.play().catch((error) => {
      console.error('Failed to play audio:', error);
    });
  };

  const pause = (id: string) => {
    if (currentPlaying === id && currentAudioRef.current) {
      currentAudioRef.current.pause();
      setCurrentPlaying(null);
      currentAudioRef.current = null;
    }
  };

  const isPlaying = (id: string) => {
    return currentPlaying === id;
  };

  return (
    <AudioContext.Provider value={{ currentPlaying, play, pause, isPlaying }}>
      {children}
    </AudioContext.Provider>
  );
}

export function useAudio() {
  const context = useContext(AudioContext);
  if (context === undefined) {
    throw new Error('useAudio must be used within an AudioProvider');
  }
  return context;
}
