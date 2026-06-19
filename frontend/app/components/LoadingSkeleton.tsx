'use client';

export function TapeCardSkeleton() {
  return (
    <div className="bg-[#1a1a1a] rounded-lg overflow-hidden animate-pulse">
      {/* Header */}
      <div className="p-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-full bg-gray-700"></div>
          <div>
            <div className="h-4 w-24 bg-gray-700 rounded mb-2"></div>
            <div className="h-3 w-16 bg-gray-700 rounded"></div>
          </div>
        </div>
        <div className="w-5 h-5 bg-gray-700 rounded"></div>
      </div>

      {/* Waveform */}
      <div className="px-4 pb-4">
        <div className="bg-[#0a0a0a] rounded-lg p-4 h-32"></div>
      </div>

      {/* Prompt */}
      <div className="px-4 pb-3">
        <div className="h-4 bg-gray-700 rounded w-full mb-2"></div>
        <div className="h-4 bg-gray-700 rounded w-3/4"></div>
      </div>

      {/* Stats */}
      <div className="px-4 pb-4 flex items-center justify-between">
        <div className="flex space-x-4">
          <div className="h-4 w-12 bg-gray-700 rounded"></div>
          <div className="h-4 w-12 bg-gray-700 rounded"></div>
        </div>
        <div className="flex space-x-2">
          <div className="h-8 w-16 bg-gray-700 rounded-lg"></div>
          <div className="h-8 w-8 bg-gray-700 rounded-lg"></div>
        </div>
      </div>

      {/* Button */}
      <div className="px-4 pb-4">
        <div className="h-10 bg-gray-700 rounded-lg"></div>
      </div>
    </div>
  );
}

export function ProfileHeaderSkeleton() {
  return (
    <div className="bg-[#1a1a1a] rounded-lg p-8 animate-pulse">
      <div className="flex flex-col md:flex-row items-start md:items-center space-y-6 md:space-y-0 md:space-x-8">
        {/* Avatar */}
        <div className="w-32 h-32 rounded-full bg-gray-700 flex-shrink-0"></div>

        {/* Info */}
        <div className="flex-1 w-full">
          <div className="h-8 w-48 bg-gray-700 rounded mb-4"></div>
          <div className="h-4 w-full bg-gray-700 rounded mb-2"></div>
          <div className="h-4 w-3/4 bg-gray-700 rounded mb-6"></div>

          <div className="flex items-center space-x-6 mb-6">
            <div className="h-4 w-20 bg-gray-700 rounded"></div>
            <div className="h-4 w-20 bg-gray-700 rounded"></div>
            <div className="h-4 w-20 bg-gray-700 rounded"></div>
            <div className="h-4 w-20 bg-gray-700 rounded"></div>
          </div>

          <div className="flex space-x-4">
            <div className="h-10 w-32 bg-gray-700 rounded-lg"></div>
            <div className="h-10 w-24 bg-gray-700 rounded-lg"></div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function FeedSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {[...Array(6)].map((_, i) => (
        <TapeCardSkeleton key={i} />
      ))}
    </div>
  );
}

export function PageLoadingSkeleton() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-[#7c3aed] mx-auto mb-4"></div>
        <p className="text-gray-400">Loading...</p>
      </div>
    </div>
  );
}

export function InlineLoadingSpinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
  };

  return (
    <div className="flex justify-center py-4">
      <div className={`animate-spin rounded-full border-t-2 border-b-2 border-[#7c3aed] ${sizeClasses[size]}`}></div>
    </div>
  );
}
