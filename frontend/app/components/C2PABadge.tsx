/**
 * C2PA Badge Component
 * 
 * Displays C2PA content credentials verification badge.
 * Shows verification status and links to full manifest.
 * 
 * Usage:
 *   <C2PABadge generationId={id} verified={true} />
 */

import React, { useState } from 'react';

interface C2PABadgeProps {
  generationId: string;
  verified?: boolean;
  parentId?: string;
  className?: string;
  showDetails?: boolean;
}

export function C2PABadge({ 
  generationId, 
  verified = false, 
  parentId,
  className = '',
  showDetails = false 
}: C2PABadgeProps) {
  const [showManifest, setShowManifest] = useState(false);
  const [manifest, setManifest] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetchManifest = async () => {
    if (manifest) {
      setShowManifest(!showManifest);
      return;
    }

    try {
      setLoading(true);
      const response = await fetch(`/api/c2pa/manifest/${generationId}`);
      
      if (response.ok) {
        const data = await response.json();
        setManifest(data);
        setShowManifest(true);
      }
    } catch (err) {
      console.error('Failed to fetch C2PA manifest:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`c2pa-badge ${className}`}>
      {/* Badge */}
      <button
        onClick={fetchManifest}
        className={`inline-flex items-center space-x-2 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
          verified
            ? 'bg-green-100 text-green-800 hover:bg-green-200 dark:bg-green-900 dark:text-green-200 dark:hover:bg-green-800'
            : 'bg-gray-100 text-gray-800 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
        }`}
        title="Click to view C2PA content credentials"
      >
        <svg 
          className="w-4 h-4" 
          fill="currentColor" 
          viewBox="0 0 20 20"
        >
          {verified ? (
            <path 
              fillRule="evenodd" 
              d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" 
              clipRule="evenodd" 
            />
          ) : (
            <path 
              fillRule="evenodd" 
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" 
              clipRule="evenodd" 
            />
          )}
        </svg>
        <span>
          {verified ? 'C2PA Verified' : 'C2PA'}
        </span>
        {loading && (
          <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        )}
      </button>

      {/* Manifest Modal */}
      {showManifest && manifest && (
        <div className="fixed inset-0 z-50 overflow-y-auto" onClick={() => setShowManifest(false)}>
          <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
            {/* Background overlay */}
            <div className="fixed inset-0 transition-opacity bg-gray-500 bg-opacity-75" />

            {/* Modal panel */}
            <div 
              className="inline-block align-bottom bg-white dark:bg-gray-800 rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-2xl sm:w-full"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="bg-gray-50 dark:bg-gray-900 px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    C2PA Content Credentials
                  </h3>
                  <button
                    onClick={() => setShowManifest(false)}
                    className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
                  >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Content */}
              <div className="px-6 py-4 max-h-96 overflow-y-auto">
                {/* Verification Status */}
                <div className={`mb-4 p-3 rounded-lg ${
                  verified 
                    ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
                    : 'bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800'
                }`}>
                  <div className="flex items-center space-x-2">
                    <svg 
                      className={`w-5 h-5 ${verified ? 'text-green-600 dark:text-green-400' : 'text-yellow-600 dark:text-yellow-400'}`}
                      fill="currentColor" 
                      viewBox="0 0 20 20"
                    >
                      <path 
                        fillRule="evenodd" 
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" 
                        clipRule="evenodd" 
                      />
                    </svg>
                    <span className={`text-sm font-medium ${
                      verified 
                        ? 'text-green-800 dark:text-green-200' 
                        : 'text-yellow-800 dark:text-yellow-200'
                    }`}>
                      {verified ? 'Verified Content Credentials' : 'Unverified Credentials'}
                    </span>
                  </div>
                </div>

                {/* Manifest Details */}
                <div className="space-y-4">
                  {/* Generator Info */}
                  {manifest.claim_generator && (
                    <div>
                      <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
                        Generator
                      </h4>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        {manifest.claim_generator}
                      </p>
                    </div>
                  )}

                  {/* Parent ID */}
                  {manifest.parent_generation_id && (
                    <div>
                      <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
                        Parent Generation
                      </h4>
                      <code className="text-xs bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">
                        {manifest.parent_generation_id}
                      </code>
                    </div>
                  )}

                  {/* AI Training Info */}
                  {manifest.assertions?.find((a: any) => a.label === 'c2pa.ai_generative_training') && (
                    <div>
                      <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
                        AI Training Data
                      </h4>
                      <div className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                        {manifest.assertions
                          .find((a: any) => a.label === 'c2pa.ai_generative_training')
                          ?.data?.training_sources?.map((source: string, i: number) => (
                            <div key={i} className="flex items-center space-x-2">
                              <span className="text-green-500">✓</span>
                              <span>{source}</span>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}

                  {/* Full Manifest (Collapsible) */}
                  <details className="mt-4">
                    <summary className="text-sm font-semibold text-gray-900 dark:text-white cursor-pointer">
                      View Full Manifest
                    </summary>
                    <pre className="mt-2 text-xs bg-gray-100 dark:bg-gray-900 p-3 rounded overflow-x-auto">
                      {JSON.stringify(manifest, null, 2)}
                    </pre>
                  </details>
                </div>
              </div>

              {/* Footer */}
              <div className="bg-gray-50 dark:bg-gray-900 px-6 py-3 border-t border-gray-200 dark:border-gray-700">
                <a
                  href="https://c2pa.org"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                >
                  Learn more about C2PA →
                </a>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default C2PABadge;