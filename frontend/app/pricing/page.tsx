'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@clerk/nextjs';
import { Music, Shield, Zap, Check, ArrowLeft, Loader2 } from 'lucide-react';

export default function PricingPage() {
  const { isSignedIn, getToken } = useAuth();
  const router = useRouter();
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null);
  const [currentTier, setCurrentTier] = useState<string>('free');

  useEffect(() => {
    const fetchSubscriptionStatus = async () => {
      if (!isSignedIn) return;
      try {
        const token = await getToken();
        const response = await fetch('/api/subscriptions/status', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (response.ok) {
          const status = await response.json();
          setCurrentTier(status.plan || 'free');
        }
      } catch (err) {
        console.error('Failed to fetch subscription status:', err);
      }
    };
    fetchSubscriptionStatus();
  }, [isSignedIn, getToken]);

  const handleUpgrade = async (plan: string) => {
    if (!isSignedIn) {
      router.push('/sign-in?redirect_url=' + encodeURIComponent('/pricing'));
      return;
    }

    setLoadingPlan(plan);
    try {
      const token = await getToken();
      const response = await fetch('/api/subscriptions/checkout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ plan }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.url) {
          window.location.href = data.url;
        } else {
          alert('Failed to initiate checkout session');
        }
      } else {
        const err = await response.json();
        alert(err.detail || 'Subscription upgrade failed');
      }
    } catch (err) {
      console.error('Checkout error:', err);
      alert('Failed to redirect to payment gateway');
    } finally {
      setLoadingPlan(null);
    }
  };

  const tiers = [
    {
      id: 'free',
      name: 'Remixa Free',
      price: '€0.00',
      description: 'Explore the power of AI remixing',
      features: [
        '5 track generations / hour',
        '10 remixes / hour',
        'Audible AudioSeal watermark',
        'Standard MP3 quality',
        'Community support',
      ],
      cta: 'Current Plan',
      popular: false,
      color: 'border-gray-800 bg-[#161616]',
    },
    {
      id: 'pro',
      name: 'Remixa Pro',
      price: '€9.99',
      period: '/month',
      description: 'Ideal for independent artists & sound creators',
      features: [
        '20 track generations / hour',
        '100 remixes / hour',
        'Shield whitelisting (own tracks)',
        'Watermark-free high quality exports',
        'Cryptographic C2PA provenance',
        'Priority email support',
      ],
      cta: 'Upgrade to Pro',
      popular: true,
      color: 'border-[#7c3aed] bg-[#1a1528] shadow-[0_0_30px_rgba(124,58,237,0.15)]',
    },
    {
      id: 'business',
      name: 'Remixa Business',
      price: '€49.99',
      period: '/month',
      description: 'Absolute safety & scale for brands & studios',
      features: [
        '100 track generations / hour',
        '500 remixes / hour',
        'Shield whitelisting (any licensed track)',
        'Batch whitelisting CSV upload',
        'Programmatic API access keys',
        'Priority GPU generation queue',
        'Dedicated account manager',
      ],
      cta: 'Go Business',
      popular: false,
      color: 'border-[#ec4899] bg-[#1d1220] shadow-[0_0_30px_rgba(236,72,153,0.15)]',
    },
  ];

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#1a1a1a]/80 backdrop-blur-md border-b border-gray-800">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/dashboard" className="flex items-center space-x-2 text-gray-400 hover:text-white transition-colors">
            <ArrowLeft className="w-5 h-5" />
            <span>Back to Explore</span>
          </Link>
          <div className="flex items-center space-x-2">
            <Music className="w-8 h-8 text-[#7c3aed]" />
            <span className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-[#7c3aed] to-[#ec4899]">
              Remixa Shield
            </span>
          </div>
          <div className="w-32 hidden md:block"></div>
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto px-4 py-16 max-w-6xl">
        <div className="text-center mb-16">
          <h1 className="text-4xl md:text-5xl font-black mb-4 tracking-tight">
            Choose Your{' '}
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#7c3aed] to-[#ec4899]">
              Creative Power
            </span>
          </h1>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">
            Supercharge your sound creation, eliminate muting risks on social platforms, and guarantee compliance with modern copyright laws.
          </p>
        </div>

        {/* Plan Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-20 items-stretch">
          {tiers.map((tier) => {
            const isCurrent = currentTier === tier.id;
            const isFree = tier.id === 'free';
            const buttonDisabled = isCurrent || (isFree && currentTier !== 'free') || loadingPlan !== null;

            return (
              <div
                key={tier.id}
                className={`relative rounded-2xl border-2 p-8 flex flex-col justify-between transition-all duration-300 hover:scale-[1.02] ${tier.color}`}
              >
                {tier.popular && (
                  <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-4 py-1 bg-gradient-to-r from-[#7c3aed] to-[#ec4899] text-xs font-bold uppercase tracking-wider rounded-full text-white shadow-md">
                    Most Popular
                  </span>
                )}

                <div>
                  <h3 className="text-2xl font-bold text-white mb-2">{tier.name}</h3>
                  <p className="text-gray-400 text-sm mb-6 min-h-[40px]">{tier.description}</p>
                  
                  <div className="flex items-baseline mb-8">
                    <span className="text-5xl font-extrabold tracking-tight">{tier.price}</span>
                    {tier.period && <span className="text-gray-400 text-lg ml-2">{tier.period}</span>}
                  </div>

                  <ul className="space-y-4 mb-8">
                    {tier.features.map((feature, i) => (
                      <li key={i} className="flex items-start text-gray-300 text-sm">
                        <Check className="w-5 h-5 text-green-400 mr-3 flex-shrink-0" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <button
                  onClick={() => !isFree && handleUpgrade(tier.id)}
                  disabled={buttonDisabled}
                  className={`w-full py-4 rounded-xl font-bold text-lg flex items-center justify-center space-x-2 transition-all ${
                    isCurrent
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30 cursor-default'
                      : isFree
                      ? 'bg-gray-800 text-gray-400 border border-gray-700 cursor-default'
                      : tier.popular
                      ? 'bg-gradient-to-r from-[#7c3aed] to-[#ec4899] text-white hover:opacity-90 shadow-lg'
                      : 'bg-white text-black hover:bg-gray-100'
                  }`}
                >
                  {loadingPlan === tier.id ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <span>{isCurrent ? 'Active Plan' : tier.cta}</span>
                  )}
                </button>
              </div>
            );
          })}
        </div>

        {/* Shield and Copyright Compliance Info Panel */}
        <div className="bg-[#121212] border border-gray-800 rounded-3xl p-8 md:p-12">
          <div className="flex flex-col lg:flex-row items-center justify-between gap-12">
            <div className="lg:w-2/3">
              <div className="flex items-center space-x-2 text-[#7c3aed] mb-4">
                <Shield className="w-6 h-6" />
                <span className="font-bold uppercase tracking-wider text-sm">Remixa Shield Protection</span>
              </div>
              <h2 className="text-3xl font-bold mb-4">Copyright Hygiene Guarantee</h2>
              <p className="text-gray-400 leading-relaxed mb-6">
                All Remixa sound generations are cleared through our platform terms and watermarked with cryptographically signed <strong>C2PA metadata</strong>. 
                Our premium <strong>Shield Whitelisting API</strong> permits Pro and Business users to register TikTok, YouTube, and Instagram URLs to whitelist license permissions instantly, guaranteeing zero mute or copyright delisting events.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-[#1a1a1a] rounded-xl p-4 border border-gray-800">
                  <h4 className="font-bold text-white mb-1">C2PA Content Credentials</h4>
                  <p className="text-xs text-gray-400">Verifiable metadata proving AI-generative origin and compliance with the EU AI Act.</p>
                </div>
                <div className="bg-[#1a1a1a] rounded-xl p-4 border border-gray-800">
                  <h4 className="font-bold text-white mb-1">AudioSeal Watermarking</h4>
                  <p className="text-xs text-gray-400">Imperceptible acoustic watermark embedded inside generated waves for verification.</p>
                </div>
              </div>
            </div>
            <div className="lg:w-1/3 bg-gradient-to-br from-[#7c3aed]/10 to-[#ec4899]/10 p-8 rounded-2xl border border-[#7c3aed]/20 text-center flex flex-col justify-center items-center">
              <Zap className="w-12 h-12 text-[#ec4899] mb-4" />
              <h3 className="text-xl font-bold mb-2">Need Custom Integration?</h3>
              <p className="text-xs text-gray-400 mb-6 leading-relaxed">
                Unlock platform-scale distribution, licensing arrays, custom team limits, and batch ingestion. Contact our business development department.
              </p>
              <a href="mailto:business@remixa.eu" className="px-6 py-2.5 bg-[#2a2a2a] text-white rounded-lg font-medium text-sm hover:bg-[#333] transition-colors">
                Contact Sales
              </a>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
