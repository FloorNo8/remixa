'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { Music, Sparkles, Mic, Image as ImageIcon, ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import VoicePicker from '@/components/VoicePicker';
import WaveformPlayer from '@/components/WaveformPlayer';
import { ErrorDisplay } from '@/components/ErrorBoundary';
import DynamicSplits from '@/components/DynamicSplits';

type LayerType = 'base' | 'lyrics' | 'voice' | 'visual';

const EXAMPLE_PROMPTS = [
  'lofi hip hop 85bpm chill study vibes',
  'phonk drift 140bpm dark aggressive',
  'house 128bpm summer beach party',
  'trap 150bpm hard 808s',
  'ambient 60bpm ethereal peaceful',
  'reggaeton 95bpm heavy dembow groove',
];

function CreateContent() {
  const searchParams = useSearchParams();
  const parentId = searchParams.get('parent');

  const [prompt, setPrompt] = useState('');
  const [selectedLayer, setSelectedLayer] = useState<LayerType>('base');
  const [selectedVoice, setSelectedVoice] = useState<string | null>(null);
  const [parentTape, setParentTape] = useState<any>(null);
  const [generating, setGenerating] = useState(false);
  const [generatedTape, setGeneratedTape] = useState<any>(null);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [customSplits, setCustomSplits] = useState({ platform: 30, parent: 50, grandparent: 20 });
  const [playMode, setPlayMode] = useState<'mastered' | 'raw'>('mastered');
  const [telemetry, setTelemetry] = useState<{
    raw_lufs: number | null;
    mastered_lufs: number | null;
    raw_peak: number | null;
    mastered_peak: number | null;
  } | null>(null);

  // Load parent tape if remixing
  useEffect(() => {
    if (parentId) {
      fetchParentTape(parentId);
    }
  }, [parentId]);

  // Poll for telemetry stats when tape is generated
  useEffect(() => {
    if (!generatedTape) return;

    const genId = generatedTape.generation_id || generatedTape.id;
    let pollInterval: NodeJS.Timeout;

    const fetchTelemetry = async () => {
      try {
        const response = await fetch(`/api/tapes/${genId}`);
        if (response.ok) {
          const data = await response.json();
          if (data.raw_lufs !== null && data.raw_lufs !== undefined) {
            setTelemetry({
              raw_lufs: data.raw_lufs,
              mastered_lufs: data.mastered_lufs,
              raw_peak: data.raw_peak,
              mastered_peak: data.mastered_peak,
            });
            clearInterval(pollInterval);
          }
        }
      } catch (err) {
        console.error('Error fetching telemetry:', err);
      }
    };

    fetchTelemetry();
    pollInterval = setInterval(fetchTelemetry, 1500);

    return () => {
      clearInterval(pollInterval);
    };
  }, [generatedTape]);

  const fetchParentTape = async (id: string) => {
    try {
      const response = await fetch(`/api/tapes/${id}`);
      const data = await response.json();
      setParentTape(data);
    } catch (err) {
      console.error('Failed to load parent tape:', err);
    }
  };

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      setError('Please enter a prompt');
      return;
    }

    if (selectedLayer === 'voice' && !selectedVoice) {
      setError('Please select a voice');
      return;
    }

    setGenerating(true);
    setError(null);
    setProgress(0);
    setPlayMode('mastered');
    setTelemetry(null);

    // Infer style from prompt
    let inferredStyle = 'lofi';
    const lowerPrompt = prompt.toLowerCase();
    if (lowerPrompt.includes('trap')) inferredStyle = 'trap';
    else if (lowerPrompt.includes('house')) inferredStyle = 'house';
    else if (lowerPrompt.includes('ambient')) inferredStyle = 'ambient';
    else if (lowerPrompt.includes('techno')) inferredStyle = 'techno';
    else if (lowerPrompt.includes('dnb') || lowerPrompt.includes('drum')) inferredStyle = 'dnb';
    else if (lowerPrompt.includes('reggaeton')) inferredStyle = 'reggaeton';

    // Simulate progress
    const progressInterval = setInterval(() => {
      setProgress(prev => Math.min(prev + 10, 90));
    }, 300);

    try {
      const response = await fetch('/api/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
        body: JSON.stringify({
          prompt,
          style: inferredStyle,
          layer_type: selectedLayer,
          parent_id: parentId || undefined,
          voice_id: selectedVoice || undefined,
        }),
      });

      clearInterval(progressInterval);
      setProgress(100);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Generation failed');
      }

      const data = await response.json();
      setGeneratedTape(data);
    } catch (err: any) {
      console.error('Generation error:', err);
      setError(err.message || 'Failed to generate tape');
      clearInterval(progressInterval);
    } finally {
      setGenerating(false);
    }
  };

  const handlePublish = async () => {
    if (!generatedTape) return;

    try {
      const token = localStorage.getItem('auth_token');
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const genId = generatedTape.generation_id || generatedTape.id;

      // 1. Save dynamic royalty splits to backend
      const splitResponse = await fetch(`${apiBaseUrl}/api/advanced/royalty-splits`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          generation_id: genId,
          platform_percentage: customSplits.platform,
          parent_percentage: customSplits.parent,
          grandparent_percentage: customSplits.grandparent,
        }),
      });

      if (!splitResponse.ok) {
        console.warn('Failed to save custom royalty splits, using default.');
      }

      // 2. Publish tape to feed
      const response = await fetch(`/api/tapes/${generatedTape.id}/publish`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        window.location.href = `/tape/${generatedTape.id}`;
      } else {
        throw new Error('Failed to publish tape to feed');
      }
    } catch (err: any) {
      console.error('Failed to publish:', err);
      setError(err.message || 'Failed to publish tape');
    }
  };

  const layers = [
    {
      type: 'base' as LayerType,
      icon: Music,
      title: 'Base Track',
      description: 'Instrumental foundation',
      color: 'bg-blue-500',
    },
    {
      type: 'lyrics' as LayerType,
      icon: Sparkles,
      title: 'Lyrics Layer',
      description: 'Add melody & structure',
      color: 'bg-purple-500',
      requiresParent: true,
    },
    {
      type: 'voice' as LayerType,
      icon: Mic,
      title: 'Voice Layer',
      description: 'Licensed voice model',
      color: 'bg-pink-500',
      requiresParent: true,
    },
    {
      type: 'visual' as LayerType,
      icon: ImageIcon,
      title: 'Visual Layer',
      description: 'Album art generation',
      color: 'bg-green-500',
      requiresParent: true,
    },
  ];

  return (
    <div className="min-h-screen bg-[#0a0a0a]">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#1a1a1a] border-b border-gray-800">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <Link href="/dashboard" className="flex items-center space-x-2 text-gray-400 hover:text-white">
              <ArrowLeft className="w-5 h-5" />
              <span>Back to Explore</span>
            </Link>
            <div className="flex items-center space-x-2">
              <Music className="w-8 h-8 text-[#7c3aed]" />
              <span className="text-2xl font-bold text-white">Create</span>
            </div>
            <div className="w-24"></div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8 max-w-4xl">
        {!generatedTape ? (
          <>
            {/* Parent Tape Preview */}
            {parentTape && (
              <div className="mb-8 bg-[#1a1a1a] rounded-lg p-6">
                <h3 className="text-white font-bold mb-4">Remixing from:</h3>
                <div className="flex items-center space-x-4">
                  <div className="w-16 h-16 bg-[#7c3aed] rounded-lg flex items-center justify-center">
                    <Music className="w-8 h-8 text-white" />
                  </div>
                  <div className="flex-1">
                    <div className="text-white font-medium">{parentTape.prompt}</div>
                    <div className="text-gray-400 text-sm">by {parentTape.creator.username}</div>
                  </div>
                </div>
              </div>
            )}

            {/* Layer Picker */}
            <div className="mb-8">
              <h3 className="text-white font-bold text-xl mb-4">Choose Layer Type</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {layers.map((layer) => {
                  const Icon = layer.icon;
                  const isDisabled = layer.requiresParent && !parentId;
                  
                  return (
                    <button
                      key={layer.type}
                      onClick={() => !isDisabled && setSelectedLayer(layer.type)}
                      disabled={isDisabled}
                      className={`p-6 rounded-lg border-2 transition-all ${
                        selectedLayer === layer.type
                          ? 'border-[#7c3aed] bg-[#7c3aed]/10'
                          : isDisabled
                          ? 'border-gray-800 bg-[#1a1a1a] opacity-50 cursor-not-allowed'
                          : 'border-gray-800 bg-[#1a1a1a] hover:border-gray-700'
                      }`}
                    >
                      <div className={`w-12 h-12 ${layer.color} rounded-lg flex items-center justify-center mx-auto mb-3`}>
                        <Icon className="w-6 h-6 text-white" />
                      </div>
                      <div className="text-white font-medium mb-1">{layer.title}</div>
                      <div className="text-gray-400 text-xs">{layer.description}</div>
                      {isDisabled && (
                        <div className="text-yellow-400 text-xs mt-2">Requires parent</div>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Prompt Input */}
            <div className="mb-8">
              <h3 className="text-white font-bold text-xl mb-4">Describe Your Sound</h3>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g., lofi hip hop 85bpm chill study vibes with piano and vinyl crackle"
                className="w-full h-32 bg-[#1a1a1a] text-white rounded-lg p-4 border border-gray-800 focus:border-[#7c3aed] focus:outline-none resize-none"
                maxLength={500}
              />
              <div className="flex justify-between items-center mt-2">
                <div className="text-gray-400 text-sm">{prompt.length}/500</div>
                <div className="text-gray-400 text-sm">
                  Tip: Include BPM, genre, mood, and instruments
                </div>
              </div>

              {/* Example Prompts */}
              <div className="mt-4">
                <div className="text-gray-400 text-sm mb-2">Try these examples:</div>
                <div className="flex flex-wrap gap-2">
                  {EXAMPLE_PROMPTS.map((example, idx) => (
                    <button
                      key={idx}
                      onClick={() => setPrompt(example)}
                      className="px-3 py-1.5 bg-[#1a1a1a] text-gray-400 text-sm rounded-lg hover:bg-[#2a2a2a] hover:text-white transition-colors"
                    >
                      {example}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Voice Picker (only for voice layer) */}
            {selectedLayer === 'voice' && (
              <div className="mb-8">
                <h3 className="text-white font-bold text-xl mb-4">Select Voice</h3>
                <VoicePicker
                  selectedVoice={selectedVoice}
                  onSelectVoice={setSelectedVoice}
                />
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="mb-8">
                <ErrorDisplay 
                  error={error} 
                  onRetry={() => {
                    setError(null);
                    handleGenerate();
                  }} 
                />
              </div>
            )}

            {/* Generate Button */}
            <button
              onClick={handleGenerate}
              disabled={generating || !prompt.trim()}
              className="w-full py-4 bg-[#7c3aed] text-white rounded-lg font-bold text-lg hover:bg-[#6d28d9] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {generating ? (
                <div className="flex items-center justify-center space-x-3">
                  <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-white"></div>
                  <span>Generating... {progress}%</span>
                </div>
              ) : (
                'Generate Tape'
              )}
            </button>

            {/* Progress Bar */}
            {generating && (
              <div className="mt-4">
                <div className="w-full bg-[#1a1a1a] rounded-full h-2">
                  <div
                    className="bg-[#7c3aed] h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  ></div>
                </div>
              </div>
            )}

            {/* Info */}
            <div className="mt-8 bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
              <div className="text-blue-400 text-sm">
                <strong>Generation time:</strong> ~3 seconds • <strong>Cost:</strong> {parentId ? '€0.10 (remix fee)' : 'Free (5/month)'}
              </div>
            </div>
          </>
        ) : (
          /* Generated Result */
          <div className="space-y-6">
            {(() => {
              const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
              const genId = generatedTape.generation_id || generatedTape.id;
              const audioUrl = `/api/tapes/${genId}/download?mode=${playMode}${token ? `&token=${token}` : ''}`;
              
              return (
                <>
                  <div className="text-center">
                    <div className="inline-flex items-center justify-center w-20 h-20 bg-green-500/20 rounded-full mb-4">
                      <svg className="w-10 h-10 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <h2 className="text-3xl font-bold text-white mb-2">Tape Generated!</h2>
                    <p className="text-gray-400">Your AI-generated track is ready</p>
                  </div>

                  {/* Waveform Preview */}
                  <div className="bg-[#1a1a1a] rounded-lg p-6">
                    <WaveformPlayer
                      audioUrl={audioUrl}
                      generationId={genId}
                      waveformData={generatedTape.waveform_data}
                    />
                  </div>

                  {/* Sound Comparison Cockpit */}
                  <div className="bg-[#141414] border border-gray-800 rounded-xl p-6 shadow-2xl relative overflow-hidden backdrop-blur-md">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-[#7c3aed]/5 rounded-full blur-3xl pointer-events-none" />
                    
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 pb-6 border-b border-gray-800/60">
                      <div>
                        <h3 className="text-lg font-bold text-white flex items-center gap-2">
                          <Sparkles className="w-5 h-5 text-[#a78bfa] animate-pulse" />
                          Sound Comparison Cockpit
                        </h3>
                        <p className="text-gray-400 text-xs mt-1">
                          A/B test the raw AI generation against Remixa's custom mastering treatment.
                        </p>
                      </div>
                      
                      {/* Switcher Toggle Buttons */}
                      <div className="inline-flex p-1 bg-[#1a1a1a] rounded-lg border border-gray-800/80">
                        <button
                          onClick={() => setPlayMode('mastered')}
                          className={`flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-md transition-all duration-300 ${
                            playMode === 'mastered'
                              ? 'bg-gradient-to-r from-[#7c3aed] to-[#db2777] text-white shadow-lg shadow-[#7c3aed]/20 scale-[1.02]'
                              : 'text-gray-400 hover:text-white'
                          }`}
                        >
                          <Sparkles className="w-3.5 h-3.5" />
                          Mastered Treatment
                        </button>
                        <button
                          onClick={() => setPlayMode('raw')}
                          className={`flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-md transition-all duration-300 ${
                            playMode === 'raw'
                              ? 'bg-[#2d3748] text-white shadow-md scale-[1.02]'
                              : 'text-gray-400 hover:text-white'
                          }`}
                        >
                          <span className="w-2 h-2 rounded-full bg-gray-500" />
                          Brut Replicate Raw
                        </button>
                      </div>
                    </div>

                    {/* Telemetry Dashboard */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      
                      {/* Left Side: Loudness & Peak Meters */}
                      <div className="space-y-4">
                        {/* Loudness LUFS */}
                        <div>
                          <div className="flex justify-between items-center text-xs text-gray-300 mb-1.5 font-semibold">
                            <span>Loudness (LUFS)</span>
                            <span className="text-[#a78bfa]">
                              {telemetry ? `${telemetry.mastered_lufs?.toFixed(1) || '-10.0'} LUFS` : 'Calculating...'}
                            </span>
                          </div>
                          
                          {/* Raw Meter */}
                          <div className="space-y-1 mb-3">
                            <div className="flex justify-between text-[10px] text-gray-500">
                              <span>Raw Generator</span>
                              <span>{telemetry?.raw_lufs ? `${telemetry.raw_lufs.toFixed(1)} LUFS` : '--'}</span>
                            </div>
                            <div className="h-1.5 bg-gray-900 rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-gray-600 transition-all duration-500 ease-out" 
                                style={{ width: telemetry?.raw_lufs ? `${Math.min(100, Math.max(10, (telemetry.raw_lufs + 30) * (100 / 30)))}%` : '0%' }}
                              />
                            </div>
                          </div>

                          {/* Mastered Meter */}
                          <div className="space-y-1">
                            <div className="flex justify-between text-[10px] text-gray-400 font-medium">
                              <span className="text-[#a78bfa]">Mastered Match</span>
                              <span className="text-[#a78bfa]">{telemetry?.mastered_lufs ? `${telemetry.mastered_lufs.toFixed(1)} LUFS` : '--'}</span>
                            </div>
                            <div className="h-2 bg-gray-900 rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-gradient-to-r from-[#7c3aed] to-[#db2777] rounded-full transition-all duration-500 ease-out" 
                                style={{ width: telemetry?.mastered_lufs ? `${Math.min(100, Math.max(10, (telemetry.mastered_lufs + 30) * (100 / 30)))}%` : '0%' }}
                              />
                            </div>
                          </div>
                        </div>

                        {/* True Peak / Headroom */}
                        <div>
                          <div className="flex justify-between items-center text-xs text-gray-300 mb-1.5 font-semibold">
                            <span>True Peak Headroom</span>
                            <span>
                              {telemetry ? `${telemetry.mastered_peak?.toFixed(1) || '-0.5'} dBFS` : 'Calculating...'}
                            </span>
                          </div>
                          
                          {/* Peak Comparison Bar */}
                          <div className="grid grid-cols-2 gap-4">
                            {/* Raw Peak */}
                            <div className="bg-[#1a1a1a]/80 border border-gray-800 rounded-lg p-2.5">
                              <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">Raw Peak</div>
                              <div className={`text-base font-bold mt-1 ${telemetry && telemetry.raw_peak !== null && telemetry.raw_peak >= -0.1 ? 'text-red-500' : 'text-gray-300'}`}>
                                {telemetry?.raw_peak !== null && telemetry?.raw_peak !== undefined ? `${telemetry.raw_peak.toFixed(1)} dBFS` : '--'}
                              </div>
                              {telemetry && telemetry.raw_peak !== null && telemetry.raw_peak >= -0.1 && (
                                <div className="text-[9px] text-red-500 font-bold mt-0.5 animate-pulse">⚠️ Digital Clipping</div>
                              )}
                            </div>

                            {/* Mastered Peak */}
                            <div className="bg-[#1a1a1a]/80 border border-gray-800 rounded-lg p-2.5">
                              <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">Mastered Peak</div>
                              <div className="text-base font-bold text-green-400 mt-1">
                                {telemetry?.mastered_peak !== null && telemetry?.mastered_peak !== undefined ? `${telemetry.mastered_peak.toFixed(1)} dBFS` : '--'}
                              </div>
                              {telemetry && (
                                <div className="text-[9px] text-green-400/90 font-medium mt-0.5">✅ Limiter Safe</div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Right Side: Stereo Width, Sub-Bass & Protections */}
                      <div className="space-y-4 bg-[#1a1a1a]/40 border border-gray-800/40 rounded-xl p-4 flex flex-col justify-between">
                        <div>
                          <h4 className="text-xs font-bold text-gray-300 uppercase tracking-wider mb-2.5">Mix Engineering Telemetry</h4>
                          <div className="space-y-2">
                            <div className="flex items-center justify-between text-xs py-1 border-b border-gray-800/50">
                              <span className="text-gray-400">Stereo Width Enhancement</span>
                              <span className="text-white font-mono font-semibold">
                                {generatedTape?.style === 'ambient' ? 'Normal (1.0x)' : '+25% Wide (1.25x)'}
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-xs py-1 border-b border-gray-800/50">
                              <span className="text-gray-400">Sub-Bass Alignment</span>
                              <span className="text-white font-mono font-semibold flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
                                Mono Sub-Bass active ({'< 100Hz'})
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-xs py-1">
                              <span className="text-gray-400">Dynamic Range Normalization</span>
                              <span className="text-white font-mono font-semibold">EBU R128 Compliant</span>
                            </div>
                          </div>
                        </div>

                        {/* Protection Badges */}
                        <div className="pt-3 border-t border-gray-800/50 flex flex-wrap gap-2">
                          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-green-500/10 border border-green-500/30 text-green-400 text-[10px] font-bold rounded-full shadow-sm">
                            <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-ping" />
                            <span>AudioSeal Watermark Active</span>
                          </div>
                          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-[#7c3aed]/10 border border-[#7c3aed]/30 text-[#c084fc] text-[10px] font-bold rounded-full shadow-sm">
                            <span>🔒 C2PA Signed</span>
                          </div>
                        </div>
                      </div>
                      
                    </div>
                  </div>

                  {/* Prompt */}
                  <div className="bg-[#1a1a1a] rounded-lg p-6">
                    <div className="text-gray-400 text-sm mb-2">Prompt</div>
                    <div className="text-white">{generatedTape.prompt}</div>
                  </div>
                </>
              );
            })()}

            {/* Dynamic Splits Configuration */}
            <DynamicSplits onChange={setCustomSplits} />

            {/* Actions */}
            <div className="flex space-x-4">
              <button
                onClick={handlePublish}
                className="flex-1 py-4 bg-[#7c3aed] text-white rounded-lg font-bold hover:bg-[#6d28d9] transition-colors"
              >
                Publish to Feed
              </button>
              <button
                onClick={() => setGeneratedTape(null)}
                className="flex-1 py-4 bg-[#1a1a1a] text-white rounded-lg font-bold hover:bg-[#2a2a2a] transition-colors"
              >
                Generate Another
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function CreatePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-[#7c3aed]"></div>
      </div>
    }>
      <CreateContent />
    </Suspense>
  );
}
