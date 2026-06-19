import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { ClerkProvider } from '@clerk/nextjs';
import { AudioProvider } from './context/AudioContext';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'EU Sound Lab - AI Music Generator',
  description: 'Create, remix, and share AI-generated music with C2PA content credentials',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider>
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
