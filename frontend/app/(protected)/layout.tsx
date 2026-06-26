import { redirect } from 'next/navigation';

const hasValidClerkKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.startsWith('pk_') 
  && !process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.includes('placeholder');

export default async function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  if (hasValidClerkKey) {
    // Only enforce auth when Clerk is properly configured
    const { auth } = await import('@clerk/nextjs/server');
    const { userId } = await auth();

    if (!userId) {
      const currentPath = '/dashboard';
      redirect(`/sign-in?redirect_url=${encodeURIComponent(currentPath)}`);
    }
  }

  return <>{children}</>;
}

