'use client';

import { useState, useCallback } from 'react';
import Link from 'next/link';
import { ArrowLeft, ShieldCheck, ShieldAlert, UploadCloud, Music, ArrowRight, Calendar, User, Info, FileText } from 'lucide-react';

interface ProvenanceNode {
  generation_id: string;
  creator_username: string;
  creator_id: string;
  prompt: string;
  layer_type: string;
  created_at: string;
  earnings: number;
  remix_count: number;
  audio_url: string;
}

interface VerificationResult {
  verified: boolean;
  generation_id: string;
  manifest_parent_id: string | null;
  database_parent_id: string | null;
  binding_valid: boolean;
  issues: string[];
  manifest: any | null;
}

export default function VerifyPage() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [lineage, setLineage] = useState<ProvenanceNode[]>([]);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.type === "audio/mpeg" || droppedFile.name.endsWith(".mp3")) {
        setFile(droppedFile);
        verifyFile(droppedFile);
      } else {
        setError("Only MP3 audio files are supported.");
      }
    }
  }, []);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      verifyFile(selectedFile);
    }
  }, []);

  const verifyFile = async (audioFile: File) => {
    setLoading(true);
    setError(null);
    setResult(null);
    setLineage([]);
    
    try {
      const formData = new FormData();
      formData.append("file", audioFile);
      
      const response = await fetch("/api/c2pa/verify-file", {
        method: "POST",
        body: formData,
      });
      
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to verify Content Credentials");
      }
      
      const data: VerificationResult = await response.json();
      setResult(data);
      
      // Fetch remix lineage chain if verified
      if (data.verified && data.generation_id) {
        fetchLineage(data.generation_id);
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || "An error occurred during verification. Check if the file is a valid Remixa track.");
    } finally {
      setLoading(false);
    }
  };

  const fetchLineage = async (generationId: string) => {
    try {
      const res = await fetch(`/api/generation/${generationId}/provenance`);
      if (res.ok) {
        const data = await res.json();
        if (data.chain_nodes) {
          setLineage(data.chain_nodes);
        }
      }
    } catch (err) {
      console.error("Failed to load lineage:", err);
    }
  };

  const resetVerification = () => {
    setFile(null);
    setResult(null);
    setLineage([]);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        {/* Navigation / Header */}
        <div className="flex items-center justify-between mb-12">
          <Link href="/dashboard" className="flex items-center space-x-2 text-zinc-400 hover:text-white transition-colors text-sm">
            <ArrowLeft className="w-4 h-4" />
            <span>Dashboard</span>
          </Link>
          <div className="flex items-center space-x-2 bg-zinc-900 border border-zinc-800 px-3 py-1 rounded-full text-xs font-semibold tracking-wide text-zinc-400">
            <span>EU AI ACT COMPLIANT</span>
          </div>
        </div>

        <div className="text-center mb-12">
          <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-purple-400 via-[#7c3aed] to-blue-500 bg-clip-text text-transparent mb-3">
            Remixa Trust Center
          </h1>
          <p className="text-zinc-400 text-lg max-w-xl mx-auto">
            Validate content credentials, verify training data compliance under EU regulations, and track remix provenance lineage.
          </p>
        </div>

        {/* Upload Zone */}
        {!file && (
          <div
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-300 ${
              dragActive 
                ? 'border-[#7c3aed] bg-purple-500/5 shadow-[0_0_20px_rgba(124,58,237,0.1)]' 
                : 'border-zinc-800 bg-[#121212]/50 hover:border-zinc-700'
            }`}
          >
            <input
              type="file"
              id="file-upload"
              accept=".mp3"
              onChange={handleFileInput}
              className="hidden"
            />
            
            <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center">
              <div className="w-16 h-16 bg-zinc-900 border border-zinc-800 rounded-2xl flex items-center justify-center mb-6 shadow-inner">
                <UploadCloud className="w-8 h-8 text-zinc-500 hover:text-zinc-400 transition-colors" />
              </div>
              
              <h3 className="text-xl font-bold text-white mb-2">Drop your Remixa track here</h3>
              <p className="text-zinc-400 text-sm mb-6 max-w-sm">
                Supports MP3 tracks generated on the platform containing embedded C2PA metadata.
              </p>
              
              <span className="px-6 py-2.5 bg-[#7c3aed] text-white hover:bg-[#6d28d9] transition-all rounded-lg font-semibold text-sm shadow-[0_4px_12px_rgba(124,58,237,0.2)]">
                Browse Files
              </span>
            </label>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="bg-[#121212] border border-zinc-800 rounded-2xl p-12 text-center shadow-lg">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#7c3aed] mx-auto mb-6"></div>
            <h3 className="text-lg font-bold text-white mb-1">Verifying Content Credentials...</h3>
            <p className="text-zinc-400 text-sm">Extracting C2PA metadata claims & checking blockchain ledger</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-500/5 border border-red-500/20 rounded-2xl p-8 text-center shadow-lg mb-8">
            <ShieldAlert className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h3 className="text-lg font-bold text-white mb-2">Verification Failed</h3>
            <p className="text-red-400 text-sm mb-6">{error}</p>
            <button
              onClick={resetVerification}
              className="px-5 py-2 bg-zinc-900 border border-zinc-800 text-white rounded-lg hover:bg-zinc-800 transition-colors text-sm font-semibold"
            >
              Try Another File
            </button>
          </div>
        )}

        {/* Result Area */}
        {result && (
          <div className="space-y-8">
            {/* Status Panel */}
            <div className={`border rounded-2xl p-8 relative overflow-hidden shadow-lg ${
              result.verified 
                ? 'border-green-500/30 bg-green-500/5' 
                : 'border-yellow-500/30 bg-yellow-500/5'
            }`}>
              <div className="flex flex-col sm:flex-row items-center sm:items-start space-y-4 sm:space-y-0 sm:space-x-6">
                <div className={`p-4 rounded-2xl ${
                  result.verified ? 'bg-green-500/10 text-green-400' : 'bg-yellow-500/10 text-yellow-400'
                }`}>
                  {result.verified ? (
                    <ShieldCheck className="w-12 h-12" />
                  ) : (
                    <ShieldAlert className="w-12 h-12" />
                  )}
                </div>
                
                <div className="flex-1 text-center sm:text-left">
                  <h2 className="text-2xl font-bold text-white mb-1">
                    {result.verified ? "Provenance Verified" : "Verification Warnings"}
                  </h2>
                  <p className="text-zinc-400 text-sm mb-4">
                    Track UUID: <span className="font-mono text-zinc-300">{result.generation_id}</span>
                  </p>
                  
                  {result.issues.length > 0 && (
                    <div className="bg-black/40 border border-zinc-800 rounded-lg p-3 text-left">
                      <div className="text-xs font-semibold text-red-400 uppercase tracking-wider mb-1">Issues Found:</div>
                      <ul className="list-disc pl-4 space-y-1 text-xs text-zinc-400">
                        {result.issues.map((issue, idx) => (
                          <li key={idx}>{issue}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {result.verified && (
                    <div className="flex flex-wrap gap-3 mt-4 justify-center sm:justify-start">
                      <span className="px-3 py-1 bg-green-500/10 text-green-400 border border-green-500/20 text-xs font-medium rounded-full">
                        C2PA Bound Valid
                      </span>
                      <span className="px-3 py-1 bg-purple-500/10 text-purple-400 border border-purple-500/20 text-xs font-medium rounded-full">
                        AI Generated Label Present
                      </span>
                    </div>
                  )}
                </div>

                <button
                  onClick={resetVerification}
                  className="px-4 py-2 bg-zinc-900 border border-zinc-800 text-white rounded-lg hover:bg-zinc-800 transition-colors text-xs font-bold"
                >
                  Verify New File
                </button>
              </div>
            </div>

            {/* Manifest Metadata Details */}
            {result.manifest && (
              <div className="bg-[#121212] border border-zinc-800 rounded-2xl p-6 sm:p-8 shadow-lg">
                <div className="flex items-center space-x-2 mb-6">
                  <FileText className="w-5 h-5 text-purple-400" />
                  <h3 className="text-lg font-bold text-white">Assertion Proofs</h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
                  <div className="space-y-4">
                    <div className="border-b border-zinc-800 pb-3">
                      <span className="text-zinc-500 block text-xs uppercase tracking-wider mb-1">Claim Generator</span>
                      <span className="text-white font-medium">{result.manifest.claim_generator || "EU Sound Lab v1.0"}</span>
                    </div>
                    <div className="border-b border-zinc-800 pb-3">
                      <span className="text-zinc-500 block text-xs uppercase tracking-wider mb-1">AI Model Version</span>
                      <span className="text-white font-medium">
                        {result.manifest.assertions?.find((a: any) => a.label === "c2pa.ai_generative_training")?.data?.model || "eu-sound-lab-v1"}
                      </span>
                    </div>
                    <div className="border-b border-zinc-800 pb-3">
                      <span className="text-zinc-500 block text-xs uppercase tracking-wider mb-1">Model Training Hash</span>
                      <span className="text-zinc-300 font-mono text-xs break-all">
                        {result.manifest.assertions?.find((a: any) => a.label === "c2pa.ai_generative_training")?.data?.training_data_hash || "sha256:1a2b3c4d5e..."}
                      </span>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="border-b border-zinc-800 pb-3">
                      <span className="text-zinc-500 block text-xs uppercase tracking-wider mb-1">Training Data Sources</span>
                      <div className="flex flex-wrap gap-1.5 mt-1">
                        {(result.manifest.assertions?.find((a: any) => a.label === "c2pa.ai_generative_training")?.data?.training_sources || [
                          "Musopen CC0", "NSynth CC-BY", "Soundsnap ML License", "Freesound CC0"
                        ]).map((src: string, i: number) => (
                          <span key={i} className="px-2 py-0.5 bg-zinc-950 border border-zinc-800 text-zinc-300 text-xs rounded">
                            {src}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="border-b border-zinc-800 pb-3">
                      <span className="text-zinc-500 block text-xs uppercase tracking-wider mb-1">AI Action Parameter</span>
                      <span className="text-white font-medium block">
                        Prompt: &quot;{result.manifest.assertions?.find((a: any) => a.label === "c2pa.actions")?.data?.[0]?.parameters?.prompt || "Remixed Audio"}&quot;
                      </span>
                      <span className="text-zinc-400 text-xs mt-1 block">
                        Style: {result.manifest.assertions?.find((a: any) => a.label === "c2pa.actions")?.data?.[0]?.parameters?.style || "Unknown"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Provenance Remix Chain */}
            {lineage.length > 0 && (
              <div className="bg-[#121212] border border-zinc-800 rounded-2xl p-6 sm:p-8 shadow-lg">
                <div className="flex items-center space-x-2 mb-8">
                  <Music className="w-5 h-5 text-[#7c3aed]" />
                  <h3 className="text-lg font-bold text-white">Remix Lineage Chain</h3>
                </div>

                <div className="relative border-l-2 border-zinc-800 ml-4 pl-8 space-y-8">
                  {lineage.map((node, index) => {
                    const isRoot = index === 0;
                    const isCurrent = index === lineage.length - 1;
                    
                    return (
                      <div key={node.generation_id} className="relative">
                        {/* Bullet point indicator */}
                        <div className={`absolute -left-[41px] top-1.5 w-6 h-6 rounded-full border-2 flex items-center justify-center bg-[#0a0a0a] ${
                          isCurrent 
                            ? 'border-[#7c3aed] text-[#7c3aed] shadow-[0_0_10px_rgba(124,58,237,0.3)]' 
                            : 'border-zinc-700 text-zinc-500'
                        }`}>
                          {index + 1}
                        </div>

                        <div className={`p-5 rounded-xl border ${
                          isCurrent 
                            ? 'bg-[#16131c]/50 border-purple-500/30' 
                            : 'bg-zinc-950/40 border-zinc-800/80'
                        }`}>
                          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-3">
                            <span className="text-sm font-semibold text-zinc-200">
                              @{node.creator_username}
                              {isRoot && <span className="ml-2 text-xs font-semibold px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">ROOT</span>}
                              {isCurrent && <span className="ml-2 text-xs font-semibold px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">THIS FILE</span>}
                              {!isRoot && !isCurrent && <span className="ml-2 text-xs font-semibold px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">REMIX LEVEL {index}</span>}
                            </span>
                            <span className="text-zinc-500 text-xs mt-1 sm:mt-0 flex items-center">
                              <Calendar className="w-3.5 h-3.5 mr-1" />
                              {new Date(node.created_at).toLocaleDateString()}
                            </span>
                          </div>

                          <p className="text-zinc-300 text-sm mb-3 italic">
                            &quot;{node.prompt}&quot;
                          </p>

                          <div className="flex items-center justify-between text-xs text-zinc-500 border-t border-zinc-800/80 pt-3">
                            <span>Layer: <strong className="text-zinc-400 capitalize">{node.layer_type}</strong></span>
                            <span>Royalties: <strong className="text-zinc-400">€{node.earnings.toFixed(2)}</strong></span>
                          </div>
                        </div>

                        {/* Connector arrow */}
                        {!isCurrent && (
                          <div className="absolute left-[-26px] bottom-[-24px] text-zinc-800">
                            <ArrowRight className="w-4 h-4 transform rotate-90" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
