'use client';

import { Flame } from 'lucide-react';

interface StreakBadgeProps {
  days: number;
  size?: 'sm' | 'md' | 'lg';
}

export default function StreakBadge({ days, size = 'md' }: StreakBadgeProps) {
  const sizeClasses = {
    sm: 'text-xs px-2 py-1',
    md: 'text-sm px-3 py-1.5',
    lg: 'text-base px-4 py-2',
  };

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  };

  const getStreakColor = () => {
    if (days >= 30) return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    if (days >= 14) return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
    if (days >= 7) return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    return 'bg-red-500/20 text-red-400 border-red-500/30';
  };

  const getStreakTitle = () => {
    if (days >= 30) return 'Legendary Streak! 🔥';
    if (days >= 14) return 'Hot Streak! 🔥';
    if (days >= 7) return 'On Fire! 🔥';
    return `${days} day streak`;
  };

  return (
    <div
      className={`inline-flex items-center space-x-1.5 rounded-full border ${getStreakColor()} ${sizeClasses[size]} font-bold`}
      title={getStreakTitle()}
    >
      <Flame className={`${iconSizes[size]} animate-pulse`} />
      <span>{days}</span>
    </div>
  );
}
