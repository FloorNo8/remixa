'use client';

import { useState, useRef } from 'react';
import Image from 'next/image';
import { Play, Pause, Check } from 'lucide-react';
import { useAudio } from '../context/AudioContext';

interface Voice {
  id: string;
  name: string;
  description: string;
  preview_url: string;
  license: string;
  artist: string;
}

const VOICES: Voice[] = [
  {
    id: 'voice-1',
    name: 'Luna',
    description: 'Soft, ethereal female voice',
    preview_url: '/audio/voices/luna-preview.mp3',
    license: 'Licensed from VoiceBank Pro',
    artist: 'Sarah Mitchell',
  },
  {
    id: 'voice-2',
    name: 'Atlas',
    description: 'Deep, powerful male voice',
    preview_url: '/audio/voices/atlas-preview.mp3',
    license: 'Licensed from VoiceBank Pro',
    artist: 'Marcus Johnson',
  },
  {
    id: 'voice-3',
    name: 'Nova',
    description: 'Energetic, upbeat female voice',
    preview_url: '/audio/voices/nova-preview.mp3',
    license: 'Licensed from VoiceBank Pro',
    artist: 'Emma Chen',
  },
  {
    id: 'voice-4',
    name: 'Echo',
    description: 'Smooth, soulful male voice',
    preview_url: '/audio/voices/echo-preview.mp3',
    license: 'Licensed from VoiceBank Pro',
    artist: 'David Williams',
  },
  {
    id: 'voice-5',
    name: 'Aria',
    description: 'Classical, operatic female voice',
    preview_url: '/audio/voices/aria-preview.mp3',
    license: 'Licensed from VoiceBank Pro',
    artist: 'Isabella Romano',
  },
];

interface VoicePickerProps {
  selectedVoice: string | null;
  onSelectVoice: (voiceId: string) => void;
}

export default function VoicePicker({ selectedVoice, onSelectVoice }: VoicePickerProps) {
  const { play, pause, isPlaying: isPlayingGlobal } = useAudio();
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const handlePlayPreview = (voice: Voice) => {
    const voicePreviewId = `voice-preview-${voice.id}`;
    
    if (isPlayingGlobal(voicePreviewId)) {
      // Stop playing
      pause(voicePreviewId);
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    } else {
      // Play new voice
      const audio = new Audio(voice.preview_url);
      audioRef.current = audio;
      
      audio.onended = () => {
        pause(voicePreviewId);
      };
      
      play(voicePreviewId, audio);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {VOICES.map((voice) => {
        const isSelected = selectedVoice === voice.id;

        const voicePreviewId = `voice-preview-${voice.id}`;
        const isPlaying = isPlayingGlobal(voicePreviewId);

        return (
          <div
            key={voice.id}
            onClick={() => onSelectVoice(voice.id)}
            className={`relative bg-[#1a1a1a] rounded-lg p-6 cursor-pointer transition-all ${
              isSelected
                ? 'border-2 border-[#7c3aed] bg-[#7c3aed]/10'
                : 'border-2 border-gray-800 hover:border-gray-700'
            }`}
          >
            {/* Selected Checkmark */}
            {isSelected && (
              <div className="absolute top-3 right-3 w-6 h-6 bg-[#7c3aed] rounded-full flex items-center justify-center">
                <Check className="w-4 h-4 text-white" />
              </div>
            )}

            {/* Voice Avatar */}
            <div className="w-16 h-16 bg-gradient-to-br from-[#7c3aed] to-[#ec4899] rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl font-bold text-white">
                {voice.name.charAt(0)}
              </span>
            </div>

            {/* Voice Info */}
            <div className="text-center mb-4">
              <h4 className="text-white font-bold text-lg mb-1">{voice.name}</h4>
              <p className="text-gray-400 text-sm mb-2">{voice.description}</p>
              <p className="text-gray-500 text-xs">by {voice.artist}</p>
            </div>

            {/* Play Preview Button */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                handlePlayPreview(voice);
              }}
              className="w-full py-2 bg-[#2a2a2a] text-white rounded-lg hover:bg-[#333] transition-colors flex items-center justify-center space-x-2"
            >
              {isPlaying ? (
                <>
                  <Pause className="w-4 h-4" />
                  <span className="text-sm">Stop Preview</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  <span className="text-sm">Play Preview</span>
                </>
              )}
            </button>

            {/* License Info */}
            <div className="mt-3 pt-3 border-t border-gray-800">
              <p className="text-gray-500 text-xs text-center">{voice.license}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
