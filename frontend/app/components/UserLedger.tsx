/**
 * User Ledger Component
 * 
 * Displays immutable transaction ledger for user earnings.
 * Shows all credits/debits with full audit trail.
 * 
 * Usage:
 *   <UserLedger userId={userId} />
 */

import React, { useState, useEffect } from 'react';

interface LedgerEntry {
  id: string;
  created_at: string;
  transaction_type: 'remix_earned' | 'payout_processed' | 'payout_reversed' | 'balance_adjustment';
  amount: number;
  license_transaction_id?: string;
  payout_id?: string;
  description: string;
  reference_id?: string;
}

interface UserLedgerProps {
  userId: string;
  className?: string;
}

export function UserLedger({ userId, className = '' }: UserLedgerProps) {
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [balance, setBalance] = useState(0);

  useEffect(() => {
    fetchLedger();
  }, [userId]);

  const fetchLedger = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/v2/ledger/${userId}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch ledger');
      }

      const data = await response.json();
      setLedger(data.entries);
      setBalance(data.balance);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const getTransactionIcon = (type: string) => {
    switch (type) {
      case 'remix_earned':
        return '💰';
      case 'payout_processed':
        return '💸';
      case 'payout_reversed':
        return '↩️';
      case 'balance_adjustment':
        return '⚖️';
      default:
        return '📝';
    }
  };

  const getTransactionColor = (amount: number) => {
    return amount >= 0 
      ? 'text-green-600 dark:text-green-400' 
      : 'text-red-600 dark:text-red-400';
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date);
  };

  if (loading) {
    return (
      <div className={`user-ledger ${className}`}>
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/4"></div>
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`user-ledger ${className}`}>
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <p className="text-sm text-red-800 dark:text-red-200">
            Error loading ledger: {error}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={`user-ledger ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Transaction Ledger
          </h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Immutable audit trail of all earnings and payouts
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Current Balance
          </p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            €{balance.toFixed(2)}
          </p>
        </div>
      </div>

      {/* Ledger Entries */}
      {ledger.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 dark:text-gray-400">
            No transactions yet. Start creating remixes to earn!
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {ledger.map((entry) => (
            <div
              key={entry.id}
              className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-3 flex-1">
                  <span className="text-2xl">{getTransactionIcon(entry.transaction_type)}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2">
                      <p className="text-sm font-medium text-gray-900 dark:text-white">
                        {entry.transaction_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </p>
                      {entry.reference_id && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300">
                          {entry.reference_id.substring(0, 8)}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                      {entry.description}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                      {formatDate(entry.created_at)}
                    </p>
                  </div>
                </div>
                <div className="text-right ml-4">
                  <p className={`text-lg font-semibold ${getTransactionColor(entry.amount)}`}>
                    {entry.amount >= 0 ? '+' : ''}€{entry.amount.toFixed(2)}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Money-Correctness Badge */}
      <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
        <div className="flex items-start space-x-3">
          <svg 
            className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" 
            fill="currentColor" 
            viewBox="0 0 20 20"
          >
            <path 
              fillRule="evenodd" 
              d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" 
              clipRule="evenodd" 
            />
          </svg>
          <div className="flex-1">
            <p className="text-sm font-medium text-blue-900 dark:text-blue-200">
              Append-Only Ledger
            </p>
            <p className="text-xs text-blue-800 dark:text-blue-300 mt-1">
              All transactions are immutable and cryptographically verified. Your balance is guaranteed by database constraints.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default UserLedger;
