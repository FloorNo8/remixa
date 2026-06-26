'use client';

import React, { useState, useEffect } from 'react';
import { Settings, Info } from 'lucide-react';

interface DynamicSplitsProps {
  onChange: (splits: {
    platform: number;
    parent: number;
    grandparent: number;
  }) => void;
}

export default function DynamicSplits({ onChange }: DynamicSplitsProps) {
  const [platform, setPlatform] = useState(30);
  const [parent, setParent] = useState(50);
  const [grandparent, setGrandparent] = useState(20);

  const total = platform + parent + grandparent;
  const isValid = Math.abs(total - 100) < 0.01;

  useEffect(() => {
    if (isValid) {
      onChange({ platform, parent, grandparent });
    }
  }, [platform, parent, grandparent, isValid]);

  const applyPreset = (platVal: number, parentVal: number, grandVal: number) => {
    setPlatform(platVal);
    setParent(parentVal);
    setGrandparent(grandVal);
  };

  return (
    <div className="bg-[#1a1a1a] rounded-lg p-6 border border-gray-800">
      <div className="flex items-center space-x-2 mb-4">
        <Settings className="w-5 h-5 text-[#7c3aed]" />
        <h3 className="text-lg font-bold text-white">Configure Remix Royalty Splits</h3>
      </div>

      <p className="text-gray-400 text-sm mb-6">
        Specify how future royalties will be distributed when other creators remix this track.
      </p>

      {/* Preset buttons */}
      <div className="flex space-x-2 mb-6">
        <button
          onClick={() => applyPreset(30, 50, 20)}
          className="px-3 py-1 bg-[#2a2a2a] text-white hover:bg-[#333] rounded text-xs transition-colors"
        >
          Default (30/50/20)
        </button>
        <button
          onClick={() => applyPreset(10, 70, 20)}
          className="px-3 py-1 bg-[#2a2a2a] text-white hover:bg-[#333] rounded text-xs transition-colors"
        >
          Platform Min (10/70/20)
        </button>
        <button
          onClick={() => applyPreset(33.3, 33.3, 33.4)}
          className="px-3 py-1 bg-[#2a2a2a] text-white hover:bg-[#333] rounded text-xs transition-colors"
        >
          Equal Splits
        </button>
      </div>

      <div className="space-y-6">
        {/* Platform Slider */}
        <div>
          <div className="flex justify-between text-sm text-gray-400 mb-1">
            <span>Platform Share</span>
            <span className="text-white font-medium">{platform.toFixed(1)}%</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="0.5"
            value={platform}
            onChange={(e) => setPlatform(parseFloat(e.target.value))}
            className="w-full h-1 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-[#7c3aed]"
          />
        </div>

        {/* Parent Creator Slider */}
        <div>
          <div className="flex justify-between text-sm text-gray-400 mb-1">
            <span>Parent Creator Share (You)</span>
            <span className="text-white font-medium">{parent.toFixed(1)}%</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="0.5"
            value={parent}
            onChange={(e) => setParent(parseFloat(e.target.value))}
            className="w-full h-1 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-[#7c3aed]"
          />
        </div>

        {/* Grandparent Creator Slider */}
        <div>
          <div className="flex justify-between text-sm text-gray-400 mb-1">
            <span>Grandparent Share (Original Creator)</span>
            <span className="text-white font-medium">{grandparent.toFixed(1)}%</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="0.5"
            value={grandparent}
            onChange={(e) => setGrandparent(parseFloat(e.target.value))}
            className="w-full h-1 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-[#7c3aed]"
          />
        </div>
      </div>

      {/* Visual representation */}
      <div className="mt-6">
        <div className="flex h-3 rounded-full overflow-hidden bg-gray-800">
          <div className="bg-blue-500" style={{ width: `${platform}%` }} title="Platform" />
          <div className="bg-green-500" style={{ width: `${parent}%` }} title="Parent" />
          <div className="bg-purple-500" style={{ width: `${grandparent}%` }} title="Grandparent" />
        </div>
        <div className="flex justify-between text-xs text-gray-400 mt-2">
          <span className="flex items-center"><span className="w-2.5 h-2.5 bg-blue-500 rounded-full mr-1" />Platform</span>
          <span className="flex items-center"><span className="w-2.5 h-2.5 bg-green-500 rounded-full mr-1" />You (Parent)</span>
          <span className="flex items-center"><span className="w-2.5 h-2.5 bg-purple-500 rounded-full mr-1" />Original (Grandparent)</span>
        </div>
      </div>

      {/* Validation alert */}
      <div className={`mt-6 p-4 rounded-lg flex items-start space-x-2 ${
        isValid ? 'bg-green-500/10 border border-green-500/30 text-green-400' : 'bg-red-500/10 border border-red-500/30 text-red-400'
      }`}>
        <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
        <div className="text-xs">
          {isValid ? (
            <span>Splits total exactly 100%. Dynamic royalty split is valid and ready to register.</span>
          ) : (
            <span>Splits must total exactly 100%. Currently: <strong>{total.toFixed(1)}%</strong>. Adjust the sliders to resolve.</span>
          )}
        </div>
      </div>
    </div>
  );
}
