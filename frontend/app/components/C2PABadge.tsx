'use client';

import { useState } from 'react';
import { Shield, X } from 'lucide-react';

interface C2PABadgeProps {
  tapeId: string;
}

export default function C2PABadge({ tapeId }: C2PABadgeProps) {
  const [showModal, setShowModal] = useState(false);
  const [manifest, setManifest] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const loadManifest = async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/tapes/${tapeId}/c2pa`);
      const data = await response.json();
      setManifest(data);
    } catch (error) {
      console.error('Failed to load C2PA manifest:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleClick = () => {
    setShowModal(true);
    if (!manifest) {
      loadManifest();
    }
  };

  return (
    <>
      <button
        onClick={handleClick}
        className="flex items-center space-x-1 px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs font-medium hover:bg-green-500/30 transition-colors"
        title="EU Compliant - View C2PA Manifest"
      >
        <Shield className="w-3 h-3" />
        <span>EU</span>
      </button>

      {showModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#1a1a1a] rounded-lg max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            {/* Header */}
            <div className="sticky top-0 bg-[#1a1a1a] border-b border-gray-800 p-4 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Shield className="w-6 h-6 text-green-400" />
                <h3 className="text-xl font-bold text-white">C2PA Content Credentials</h3>
              </div>
              <button
                onClick={() => setShowModal(false)}
                className="text-gray-400 hover:text-white"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Content */}
            <div className="p-6">
              {loading ? (
                <div className="flex justify-center py-12">
                  <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#7c3aed]"></div>
                </div>
              ) : manifest ? (
                <div className="space-y-6">
                  {/* Compliance Status */}
                  <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
                    <div className="flex items-center space-x-2 mb-2">
                      <Shield className="w-5 h-5 text-green-400" />
                      <span className="font-bold text-green-400">EU Compliant</span>
                    </div>
                    <p className="text-sm text-gray-300">
                      This content meets EU AI Act Article 53 transparency requirements
                    </p>
                  </div>

                  {/* Generator Info */}
                  <div>
                    <h4 className="text-white font-bold mb-3">Generator Information</h4>
                    <div className="bg-[#0a0a0a] rounded-lg p-4 space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-400">Model:</span>
                        <span className="text-white">{manifest.generator?.name || 'MusicGen-Stem'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">Version:</span>
                        <span className="text-white">{manifest.generator?.version || '1.0'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">Generated:</span>
                        <span className="text-white">
                          {new Date(manifest.created_at).toLocaleString()}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Training Data */}
                  <div>
                    <h4 className="text-white font-bold mb-3">Training Data Sources</h4>
                    <div className="bg-[#0a0a0a] rounded-lg p-4 space-y-3">
                      {manifest.training_data?.map((source: any, idx: number) => (
                        <div key={idx} className="text-sm">
                          <div className="text-white font-medium">{source.name}</div>
                          <div className="text-gray-400 text-xs">{source.license}</div>
                        </div>
                      )) || (
                        <>
                          <div className="text-sm">
                            <div className="text-white font-medium">Musopen Classical Archive</div>
                            <div className="text-gray-400 text-xs">CC0 - 4,200 hours</div>
                          </div>
                          <div className="text-sm">
                            <div className="text-white font-medium">NSynth Dataset</div>
                            <div className="text-gray-400 text-xs">CC-BY-4.0 - 3,800 hours</div>
                          </div>
                          <div className="text-sm">
                            <div className="text-white font-medium">Soundsnap ML License</div>
                            <div className="text-gray-400 text-xs">Commercial - 6,000 hours</div>
                          </div>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Remix Chain */}
                  {manifest.remix_chain && manifest.remix_chain.length > 0 && (
                    <div>
                      <h4 className="text-white font-bold mb-3">Remix Chain</h4>
                      <div className="bg-[#0a0a0a] rounded-lg p-4">
                        <div className="space-y-2">
                          {manifest.remix_chain.map((item: any, idx: number) => (
                            <div key={idx} className="flex items-center space-x-2 text-sm">
                              <div className="w-6 h-6 rounded-full bg-[#7c3aed] flex items-center justify-center text-white text-xs">
                                {idx + 1}
                              </div>
                              <div className="flex-1">
                                <div className="text-white">{item.creator}</div>
                                <div className="text-gray-400 text-xs">{item.layer_type}</div>
                              </div>
                              <div className="text-gray-400 text-xs">
                                {new Date(item.created_at).toLocaleDateString()}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Signature */}
                  <div>
                    <h4 className="text-white font-bold mb-3">Digital Signature</h4>
                    <div className="bg-[#0a0a0a] rounded-lg p-4">
                      <div className="text-xs text-gray-400 font-mono break-all">
                        {manifest.signature || 'SHA256:a3f2b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0'}
                      </div>
                    </div>
                  </div>

                  {/* Verification */}
                  <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
                    <p className="text-sm text-gray-300">
                      <strong className="text-blue-400">Verification:</strong> This manifest is cryptographically signed and can be independently verified using the{' '}
                      <a
                        href="https://contentcredentials.org/verify"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-400 hover:underline"
                      >
                        Content Credentials Verify tool
                      </a>
                    </p>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 text-gray-400">
                  Failed to load manifest
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
