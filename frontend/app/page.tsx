import Link from 'next/link';
import { Music, Shield, Zap, Globe, CheckCircle } from 'lucide-react';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      {/* Header */}
      <header className="container mx-auto px-4 py-6">
        <nav className="flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <Music className="w-8 h-8 text-blue-600" />
            <span className="text-2xl font-bold">EU Sound Lab</span>
          </div>
          <div className="space-x-4">
            <Link href="/pricing" className="text-gray-600 hover:text-gray-900">
              Pricing
            </Link>
            <Link href="/compliance" className="text-gray-600 hover:text-gray-900">
              Compliance
            </Link>
            <Link href="/auth/login" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              Sign In
            </Link>
          </div>
        </nav>
      </header>

      {/* Hero Section */}
      <section className="container mx-auto px-4 py-20 text-center">
        <h1 className="text-5xl font-bold mb-6">
          AI Music for TikTok Creators
          <br />
          <span className="text-blue-600">100% EU Compliant</span>
        </h1>
        <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
          Generate copyright-safe instrumental tracks in seconds. 
          Trained only on licensed data. Full GDPR, AI Act, and DSA compliance.
        </p>
        <div className="flex justify-center space-x-4">
          <Link href="/auth/signup" className="px-8 py-4 bg-blue-600 text-white rounded-lg text-lg font-semibold hover:bg-blue-700">
            Start Free Trial
          </Link>
          <Link href="/generate" className="px-8 py-4 border-2 border-blue-600 text-blue-600 rounded-lg text-lg font-semibold hover:bg-blue-50">
            Try Demo
          </Link>
        </div>
        <p className="mt-4 text-sm text-gray-500">
          5 free tracks/month • No credit card required
        </p>
      </section>

      {/* Features */}
      <section className="container mx-auto px-4 py-20">
        <div className="grid md:grid-cols-3 gap-8">
          <div className="p-6 bg-white rounded-lg shadow-sm">
            <Zap className="w-12 h-12 text-blue-600 mb-4" />
            <h3 className="text-xl font-bold mb-2">Lightning Fast</h3>
            <p className="text-gray-600">
              Generate 15-second tracks in under 3 seconds. Perfect for TikTok, Reels, and Shorts.
            </p>
          </div>
          
          <div className="p-6 bg-white rounded-lg shadow-sm">
            <Shield className="w-12 h-12 text-blue-600 mb-4" />
            <h3 className="text-xl font-bold mb-2">Legally Bulletproof</h3>
            <p className="text-gray-600">
              Trained only on licensed data. C2PA credentials embedded. €10k indemnity per track.
            </p>
          </div>
          
          <div className="p-6 bg-white rounded-lg shadow-sm">
            <Globe className="w-12 h-12 text-blue-600 mb-4" />
            <h3 className="text-xl font-bold mb-2">EU Compliant</h3>
            <p className="text-gray-600">
              Full GDPR, AI Act Art 53, and DSA compliance. EU servers only. VAT MOSS automated.
            </p>
          </div>
        </div>
      </section>

      {/* Compliance Badges */}
      <section className="container mx-auto px-4 py-20 bg-gray-50 rounded-lg">
        <h2 className="text-3xl font-bold text-center mb-12">Regulatory Compliance</h2>
        <div className="grid md:grid-cols-4 gap-6 text-center">
          <div>
            <CheckCircle className="w-16 h-16 text-green-600 mx-auto mb-4" />
            <h4 className="font-bold mb-2">EU AI Act</h4>
            <p className="text-sm text-gray-600">Art 53 transparency obligations met</p>
          </div>
          <div>
            <CheckCircle className="w-16 h-16 text-green-600 mx-auto mb-4" />
            <h4 className="font-bold mb-2">GDPR</h4>
            <p className="text-sm text-gray-600">Data export & deletion within 30 days</p>
          </div>
          <div>
            <CheckCircle className="w-16 h-16 text-green-600 mx-auto mb-4" />
            <h4 className="font-bold mb-2">DSA</h4>
            <p className="text-sm text-gray-600">Content moderation & reporting</p>
          </div>
          <div>
            <CheckCircle className="w-16 h-16 text-green-600 mx-auto mb-4" />
            <h4 className="font-bold mb-2">VAT MOSS</h4>
            <p className="text-sm text-gray-600">Automated quarterly filing</p>
          </div>
        </div>
      </section>

      {/* Training Data Transparency */}
      <section className="container mx-auto px-4 py-20">
        <h2 className="text-3xl font-bold text-center mb-12">Training Data Sources</h2>
        <div className="max-w-3xl mx-auto bg-white p-8 rounded-lg shadow-sm">
          <p className="text-gray-600 mb-6">
            Our model is trained exclusively on licensed and public domain data:
          </p>
          <ul className="space-y-4">
            <li className="flex items-start">
              <CheckCircle className="w-6 h-6 text-green-600 mr-3 flex-shrink-0 mt-1" />
              <div>
                <strong>Musopen Classical Archive</strong> (CC0) - 4,200 hours
                <p className="text-sm text-gray-500">Public domain classical recordings</p>
              </div>
            </li>
            <li className="flex items-start">
              <CheckCircle className="w-6 h-6 text-green-600 mr-3 flex-shrink-0 mt-1" />
              <div>
                <strong>NSynth Dataset</strong> (CC-BY-4.0) - 3,800 hours
                <p className="text-sm text-gray-500">Google Magenta instrumental dataset</p>
              </div>
            </li>
            <li className="flex items-start">
              <CheckCircle className="w-6 h-6 text-green-600 mr-3 flex-shrink-0 mt-1" />
              <div>
                <strong>Soundsnap ML License</strong> (Commercial) - 6,000 hours
                <p className="text-sm text-gray-500">Licensed for machine learning training</p>
              </div>
            </li>
            <li className="flex items-start">
              <CheckCircle className="w-6 h-6 text-green-600 mr-3 flex-shrink-0 mt-1" />
              <div>
                <strong>Freesound CC0</strong> (CC0) - 3,000 hours
                <p className="text-sm text-gray-500">Community-contributed instrumental sounds</p>
              </div>
            </li>
          </ul>
          <p className="mt-6 text-sm text-gray-500">
            <strong>Total:</strong> 17,000 hours • <strong>Vocal content:</strong> None • <strong>Artist likeness:</strong> None
          </p>
          <Link href="/compliance" className="mt-6 inline-block text-blue-600 hover:underline">
            View full training data manifest →
          </Link>
        </div>
      </section>

      {/* Pricing Preview */}
      <section className="container mx-auto px-4 py-20 bg-blue-50 rounded-lg">
        <h2 className="text-3xl font-bold text-center mb-12">Simple, Transparent Pricing</h2>
        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          <div className="bg-white p-8 rounded-lg shadow-sm">
            <h3 className="text-2xl font-bold mb-4">Free</h3>
            <p className="text-4xl font-bold mb-6">€0<span className="text-lg text-gray-500">/month</span></p>
            <ul className="space-y-3 mb-8">
              <li className="flex items-center">
                <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                5 tracks/month
              </li>
              <li className="flex items-center">
                <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                Watermarked
              </li>
              <li className="flex items-center">
                <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                Non-commercial use
              </li>
            </ul>
            <Link href="/auth/signup" className="block w-full py-3 text-center border-2 border-blue-600 text-blue-600 rounded-lg font-semibold hover:bg-blue-50">
              Get Started
            </Link>
          </div>

          <div className="bg-blue-600 text-white p-8 rounded-lg shadow-lg transform scale-105">
            <div className="text-sm font-bold mb-2">MOST POPULAR</div>
            <h3 className="text-2xl font-bold mb-4">Pro</h3>
            <p className="text-4xl font-bold mb-6">€5<span className="text-lg opacity-75">/month</span></p>
            <ul className="space-y-3 mb-8">
              <li className="flex items-center">
                <CheckCircle className="w-5 h-5 mr-2" />
                100 tracks/month
              </li>
              <li className="flex items-center">
                <CheckCircle className="w-5 h-5 mr-2" />
                No watermark
              </li>
              <li className="flex items-center">
                <CheckCircle className="w-5 h-5 mr-2" />
                Commercial license
              </li>
              <li className="flex items-center">
                <CheckCircle className="w-5 h-5 mr-2" />
                C2PA credentials
              </li>
              <li className="flex items-center">
                <CheckCircle className="w-5 h-5 mr-2" />
                €10k indemnity
              </li>
            </ul>
            <Link href="/auth/signup?plan=pro" className="block w-full py-3 text-center bg-white text-blue-600 rounded-lg font-semibold hover:bg-gray-100">
              Start Free Trial
            </Link>
          </div>

          <div className="bg-white p-8 rounded-lg shadow-sm">
            <h3 className="text-2xl font-bold mb-4">Business</h3>
            <p className="text-4xl font-bold mb-6">€49<span className="text-lg text-gray-500">/month</span></p>
            <ul className="space-y-3 mb-8">
              <li className="flex items-center">
                <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                1,000 tracks/month
              </li>
              <li className="flex items-center">
                <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                API access
              </li>
              <li className="flex items-center">
                <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                White-label
              </li>
              <li className="flex items-center">
                <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                Priority support
              </li>
            </ul>
            <Link href="/auth/signup?plan=business" className="block w-full py-3 text-center border-2 border-blue-600 text-blue-600 rounded-lg font-semibold hover:bg-blue-50">
              Contact Sales
            </Link>
          </div>
        </div>
        <p className="text-center mt-8 text-sm text-gray-600">
          Prices exclude VAT (17-27% depending on your EU country)
        </p>
      </section>

      {/* Footer */}
      <footer className="container mx-auto px-4 py-12 border-t mt-20">
        <div className="grid md:grid-cols-4 gap-8">
          <div>
            <div className="flex items-center space-x-2 mb-4">
              <Music className="w-6 h-6 text-blue-600" />
              <span className="font-bold">EU Sound Lab</span>
            </div>
            <p className="text-sm text-gray-600">
              AI music generation for TikTok creators. 100% EU compliant.
            </p>
          </div>
          <div>
            <h4 className="font-bold mb-4">Product</h4>
            <ul className="space-y-2 text-sm text-gray-600">
              <li><Link href="/generate">Generate</Link></li>
              <li><Link href="/pricing">Pricing</Link></li>
              <li><Link href="/api-docs">API Docs</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="font-bold mb-4">Compliance</h4>
            <ul className="space-y-2 text-sm text-gray-600">
              <li><Link href="/compliance">AI Act</Link></li>
              <li><Link href="/privacy">GDPR</Link></li>
              <li><Link href="/terms">Terms</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="font-bold mb-4">Company</h4>
            <ul className="space-y-2 text-sm text-gray-600">
              <li><Link href="/about">About</Link></li>
              <li><Link href="/contact">Contact</Link></li>
              <li><Link href="/blog">Blog</Link></li>
            </ul>
          </div>
        </div>
        <div className="mt-12 pt-8 border-t text-center text-sm text-gray-600">
          <p>© 2026 Floor No 8 SRL. All rights reserved.</p>
          <p className="mt-2">VAT: DK12345678 • Registered in Denmark</p>
        </div>
      </footer>
    </div>
  );
}
