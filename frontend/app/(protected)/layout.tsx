import { auth } from '@clerk/nextjs/server';
import { redirect } from 'next/navigation';

export default async function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { userId } = await auth();

  if (!userId) {
    // Redirect to sign-in with return URL
    const currentPath = '/dashboard'; // Default fallback
    redirect(`/sign-in?redirect_url=${encodeURIComponent(currentPath)}`);
  }

  return <>{children}</>;
}
