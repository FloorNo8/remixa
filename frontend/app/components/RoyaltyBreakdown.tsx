/**
 * Royalty Breakdown Component
 * 
 * Displays money-correctness guaranteed royalty splits for a remix.
 * Shows conservation invariant enforcement and split distribution.
 * 
 * Usage:
 *   <RoyaltyBreakdown generation={generation} />
 */

import React from 'react';

interface Generation {
  id: string;
  parent_id?: string;
  grandparent_id?: string;
  amount: number;
  platform_fee: number;
  creator_share: number;
  grandparent_share?: number;
  parent_creator?: {
    username: string;
    id: string;
  };
  grandparent_creator?: {
    username: string;
    id: string;
  };
}

interface RoyaltyBreakdownProps {
  generation: Generation;
  className?: string;
}

export function RoyaltyBreakdown({ generation, className = '' }: RoyaltyBreakdownProps) {
  const hasGrandparent = generation.grandparent_share && generation.grandparent_share > 0;
  const total = generation.amount;
  const platformFee = generation.platform_fee;
  const creatorShare = generation.creator_share;
  const grandparentShare = generation.grandparent_share || 0;
  
  // Verify conservation invariant (should always be true due to DB constraint)
  const conservationHolds = Math.abs(
    total - (platformFee + creatorShare + grandparentShare)
  ) < 0.001;

  return (
    <div className={`royalty-breakdown bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Royalty Split
        </h3>
        {conservationHolds && (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
            ✓ Money-Correct
          </span>
        )}
      </div>

      <div className="space-y-3">
        {/* Platform Fee */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-full bg-blue-500"></div>
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Platform Fee
            </span>
          </div>
          <span className="text-sm font-medium text-gray-900 dark:text-white">
            €{platformFee.toFixed(2)}
          </span>
        </div>

        {/* Parent Creator Share */}
        {generation.parent_creator && (
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 rounded-full bg-green-500"></div>
              <span className="text-sm text-gray-700 dark:text-gray-300">
                Parent Creator
                <span className="ml-1 text-xs text-gray-500">
                  (@{generation.parent_creator.username})
                </span>
              </span>
            </div>
            <span className="text-sm font-medium text-gray-900 dark:text-white">
              €{creatorShare.toFixed(2)}
            </span>
          </div>
        )}

        {/* Grandparent Creator Share */}
        {hasGrandparent && generation.grandparent_creator && (
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 rounded-full bg-purple-500"></div>
              <span className="text-sm text-gray-700 dark:text-gray-300">
                Grandparent Creator
                <span className="ml-1 text-xs text-gray-500">
                  (@{generation.grandparent_creator.username})
                </span>
              </span>
            </div>
            <span className="text-sm font-medium text-gray-900 dark:text-white">
              €{grandparentShare.toFixed(2)}
            </span>
          </div>
        )}

        {/* Total */}
        <div className="pt-3 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-900 dark:text-white">
              Total
            </span>
            <span className="text-sm font-semibold text-gray-900 dark:text-white">
              €{total.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* Money-Correctness Guarantee */}
      <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-md">
        <div className="flex items-start space-x-2">
          <svg 
            className="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" 
            fill="currentColor" 
            viewBox="0 0 20 20"
          >
            <path 
              fillRule="evenodd" 
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" 
              clipRule="evenodd" 
            />
          </svg>
          <div className="flex-1">
            <p className="text-xs font-medium text-green-800 dark:text-green-200">
              Conservation Guaranteed
            </p>
            <p className="text-xs text-green-700 dark:text-green-300 mt-1">
              Database constraint enforces: €{total.toFixed(2)} = €{platformFee.toFixed(2)} + €{creatorShare.toFixed(2)}
              {hasGrandparent && ` + €${grandparentShare.toFixed(2)}`}
            </p>
          </div>
        </div>
      </div>

      {/* Visual Bar */}
      <div className="mt-4">
        <div className="flex h-2 rounded-full overflow-hidden">
          <div 
            className="bg-blue-500" 
            style={{ width: `${(platformFee / total) * 100}%` }}
            title={`Platform: €${platformFee.toFixed(2)}`}
          />
          <div 
            className="bg-green-500" 
            style={{ width: `${(creatorShare / total) * 100}%` }}
            title={`Parent: €${creatorShare.toFixed(2)}`}
          />
          {hasGrandparent && (
            <div 
              className="bg-purple-500" 
              style={{ width: `${(grandparentShare / total) * 100}%` }}
              title={`Grandparent: €${grandparentShare.toFixed(2)}`}
            />
          )}
        </div>
      </div>

      {/* Learn More Link */}
      <div className="mt-4 text-center">
        <a 
          href="/docs/royalties" 
          className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
        >
          Learn how royalties work →
        </a>
      </div>
    </div>
  );
}

export default RoyaltyBreakdown;
