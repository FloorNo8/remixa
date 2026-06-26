'use client';

import React from 'react';

export function ClerkProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export function useAuth() {
  return {
    isLoaded: true,
    isSignedIn: true,
    userId: 'user_2T7gMOCKDEVUSERID12345',
    orgId: null,
    orgRole: null,
    orgSlug: null,
    actor: null,
    sessionId: 'mock_session_id',
    getToken: async () => 'mock-clerk-jwt-token',
    signOut: async () => {},
  };
}

export function useUser() {
  return {
    isLoaded: true,
    isSignedIn: true,
    user: {
      id: 'user_2T7gMOCKDEVUSERID12345',
      username: 'developer',
      primaryEmailAddress: {
        emailAddress: 'developer@remixa.eu',
      },
      imageUrl: 'https://img.clerk.com/placeholder',
    },
  };
}

// Server-side mock exports
export async function auth() {
  return {
    userId: 'user_2T7gMOCKDEVUSERID12345',
    sessionClaims: {},
  };
}

export const clerkClient = {
  users: {
    getUser: async () => ({
      id: 'user_2T7gMOCKDEVUSERID12345',
      username: 'developer',
      emailAddresses: [{ emailAddress: 'developer@remixa.eu' }],
    }),
  },
};
