/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    domains: ['r2.remixa.eu', 'images.clerk.dev', 'img.clerk.com'],
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
  },
  // Enable React strict mode for better development experience
  reactStrictMode: true,
  // Optimize production builds
  swcMinify: true,

  webpack: (config, { isServer }) => {
    const hasValidClerkKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.startsWith('pk_') 
      && !process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.includes('placeholder');

    if (!hasValidClerkKey) {
      config.resolve.alias['@clerk/nextjs$'] = require.resolve('./app/clerk-mock.tsx');
      config.resolve.alias['@clerk/nextjs/server'] = require.resolve('./app/clerk-mock.tsx');
    }
    return config;
  },
  
  // Security headers
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-eval' 'unsafe-inline' https://clerk.com https://*.clerk.accounts.dev",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: https: blob:",
              "font-src 'self' data:",
              "connect-src 'self' https://api.remixa.eu https://*.clerk.accounts.dev https://clerk.com wss://*.clerk.accounts.dev",
              "media-src 'self' https://r2.remixa.eu blob:",
              "frame-src 'self' https://clerk.com https://*.clerk.accounts.dev",
              "worker-src 'self' blob:",
            ].join('; '),
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()',
          },
        ],
      },
    ];
  },

  async rewrites() {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/explore',
        destination: `${apiBaseUrl}/api/v2/explore`,
      },
      {
        source: '/api/tapes/:id/publish',
        destination: `${apiBaseUrl}/api/v2/generations/:id/publish`,
      },
      {
        source: '/api/tapes/:id/download',
        destination: `${apiBaseUrl}/api/v2/generations/:id/download`,
      },
      {
        source: '/api/tapes/:id',
        destination: `${apiBaseUrl}/api/v2/generations/:id`,
      },
      {
        source: '/api/earnings/withdraw',
        destination: `${apiBaseUrl}/api/v2/payout`,
      },
      {
        source: '/api/earnings',
        destination: `${apiBaseUrl}/api/v2/earnings`,
      },
      {
        source: '/api/stripe/:path*',
        destination: `${apiBaseUrl}/api/stripe/:path*`,
      },
      {
        source: '/api/generate',
        destination: `${apiBaseUrl}/api/v1/generate`,
      },
      {
        source: '/api/c2pa/:path*',
        destination: `${apiBaseUrl}/api/c2pa/:path*`,
      },
      {
        source: '/api/generation/:id/provenance',
        destination: `${apiBaseUrl}/api/generation/:id/provenance`,
      },
      {
        source: '/api/subscriptions/:path*',
        destination: `${apiBaseUrl}/api/subscriptions/:path*`,
      },
      {
        source: '/api/shield/:path*',
        destination: `${apiBaseUrl}/api/v1/shield/:path*`,
      },
      {
        source: '/api/analytics/:path*',
        destination: `${apiBaseUrl}/api/analytics/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
