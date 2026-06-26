import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { ClerkProvider } from '@clerk/nextjs';
import { AudioProvider } from './context/AudioContext';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

const hasValidClerkKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.startsWith('pk_') 
  && !process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.includes('placeholder');

// Fallback dummy key to prevent ClerkProvider from failing initialization
const clerkPublishableKey = hasValidClerkKey 
  ? process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY 
  : "pk_test_dGVzdC1rZXktMTIuY2xlcmsuYWNjb3VudHMuZGV2JA";

export const metadata: Metadata = {
  title: 'Remixa — AI Music Generator',
  description: 'Create, remix, and share AI-generated music with C2PA content credentials and Double-Shield verification',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider publishableKey={clerkPublishableKey}>
      <html lang="en">
        <body className={inter.className}>
          <AudioProvider>
            {children}
          </AudioProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
