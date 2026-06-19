import { redirect } from 'next/navigation';
import Link from 'next/link';

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // TODO: Implement proper JWT-based authentication check
  // For now, admin panel is accessible (will be protected by backend RBAC)
  // In production, verify JWT token and check admin role from backend

  return (
    <div className="min-h-screen bg-[#0a0a0a]">
      <nav className="border-b border-zinc-800 bg-black/50 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-8">
              <h1 className="text-xl font-bold text-white">🛡️ Admin Panel</h1>
              <div className="flex gap-4">
                <Link
                  href="/admin"
                  className="text-zinc-400 hover:text-white transition-colors"
                >
                  Dashboard
                </Link>
                <Link
                  href="/admin/moderation"
                  className="text-zinc-400 hover:text-white transition-colors"
                >
                  Moderation
                </Link>
                <Link
                  href="/admin/users"
                  className="text-zinc-400 hover:text-white transition-colors"
                >
                  Users
                </Link>
                <Link
                  href="/admin/content"
                  className="text-zinc-400 hover:text-white transition-colors"
                >
                  Content
                </Link>
                <Link
                  href="/admin/vat"
                  className="text-zinc-400 hover:text-white transition-colors"
                >
                  VAT
                </Link>
                <Link
                  href="/admin/system"
                  className="text-zinc-400 hover:text-white transition-colors"
                >
                  System
                </Link>
              </div>
            </div>
            <Link
              href="/dashboard"
              className="text-sm text-zinc-400 hover:text-white transition-colors"
            >
              ← Back to App
            </Link>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-4 py-8">{children}</main>
    </div>
  );
}
