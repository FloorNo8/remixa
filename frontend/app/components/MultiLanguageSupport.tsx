/**
 * Multi-Language Support Component
 * 
 * Provides internationalization (i18n) for Remixa platform.
 * Supports 10+ languages with RTL support.
 * 
 * Usage:
 *   import { useTranslation, LanguageSelector } from './MultiLanguageSupport'
 *   
 *   const { t, language, setLanguage } = useTranslation()
 *   <p>{t('common.welcome')}</p>
 */

import React, { createContext, useContext, useState, useEffect } from 'react';

// Supported languages
export const SUPPORTED_LANGUAGES = {
  'en': { name: 'English', nativeName: 'English', rtl: false },
  'es': { name: 'Spanish', nativeName: 'Español', rtl: false },
  'fr': { name: 'French', nativeName: 'Français', rtl: false },
  'de': { name: 'German', nativeName: 'Deutsch', rtl: false },
  'it': { name: 'Italian', nativeName: 'Italiano', rtl: false },
  'pt': { name: 'Portuguese', nativeName: 'Português', rtl: false },
  'nl': { name: 'Dutch', nativeName: 'Nederlands', rtl: false },
  'pl': { name: 'Polish', nativeName: 'Polski', rtl: false },
  'ru': { name: 'Russian', nativeName: 'Русский', rtl: false },
  'ja': { name: 'Japanese', nativeName: '日本語', rtl: false },
  'zh': { name: 'Chinese', nativeName: '中文', rtl: false },
  'ar': { name: 'Arabic', nativeName: 'العربية', rtl: true },
  'he': { name: 'Hebrew', nativeName: 'עברית', rtl: true }
};

// Translation keys (English as base)
const translations: Record<string, Record<string, string>> = {
  en: {
    // Common
    'common.welcome': 'Welcome to Remixa',
    'common.loading': 'Loading...',
    'common.error': 'Error',
    'common.success': 'Success',
    'common.cancel': 'Cancel',
    'common.save': 'Save',
    'common.delete': 'Delete',
    'common.edit': 'Edit',
    'common.create': 'Create',
    
    // Navigation
    'nav.dashboard': 'Dashboard',
    'nav.create': 'Create',
    'nav.earnings': 'Earnings',
    'nav.profile': 'Profile',
    'nav.settings': 'Settings',
    
    // Royalties
    'royalty.breakdown': 'Royalty Breakdown',
    'royalty.platform_fee': 'Platform Fee',
    'royalty.parent_creator': 'Parent Creator',
    'royalty.grandparent_creator': 'Grandparent Creator',
    'royalty.total': 'Total',
    'royalty.guaranteed': 'Money-Correct Guarantee',
    'royalty.conservation': 'Conservation Guaranteed',
    'royalty.learn_more': 'Learn how royalties work',
    
    // Ledger
    'ledger.title': 'Transaction Ledger',
    'ledger.subtitle': 'Immutable audit trail of all earnings and payouts',
    'ledger.balance': 'Current Balance',
    'ledger.no_transactions': 'No transactions yet. Start creating remixes to earn!',
    'ledger.append_only': 'Append-Only Ledger',
    'ledger.guarantee': 'All transactions are immutable and cryptographically verified.',
    
    // C2PA
    'c2pa.verified': 'C2PA Verified',
    'c2pa.credentials': 'Content Credentials',
    'c2pa.generator': 'Generator',
    'c2pa.parent': 'Parent Generation',
    'c2pa.training': 'AI Training Data',
    'c2pa.manifest': 'View Full Manifest',
    'c2pa.learn': 'Learn more about C2PA',
    
    // Advanced Features
    'advanced.multi_currency': 'Multi-Currency',
    'advanced.dynamic_splits': 'Custom Splits',
    'advanced.pools': 'Collaboration Pools',
    'advanced.blockchain': 'Blockchain',
    'advanced.instant_payouts': 'Instant Payouts',
    
    // Errors
    'error.network': 'Network error. Please try again.',
    'error.unauthorized': 'Unauthorized. Please log in.',
    'error.not_found': 'Not found.',
    'error.server': 'Server error. Please try again later.'
  },
  
  es: {
    'common.welcome': 'Bienvenido a Remixa',
    'common.loading': 'Cargando...',
    'common.error': 'Error',
    'common.success': 'Éxito',
    'royalty.breakdown': 'Desglose de Regalías',
    'royalty.platform_fee': 'Tarifa de Plataforma',
    'ledger.title': 'Libro de Transacciones',
    'c2pa.verified': 'Verificado C2PA'
  },
  
  fr: {
    'common.welcome': 'Bienvenue sur Remixa',
    'common.loading': 'Chargement...',
    'royalty.breakdown': 'Répartition des Redevances',
    'ledger.title': 'Registre des Transactions',
    'c2pa.verified': 'Vérifié C2PA'
  },
  
  de: {
    'common.welcome': 'Willkommen bei Remixa',
    'common.loading': 'Laden...',
    'royalty.breakdown': 'Lizenzgebühren-Aufschlüsselung',
    'ledger.title': 'Transaktionsbuch',
    'c2pa.verified': 'C2PA Verifiziert'
  },
  
  ar: {
    'common.welcome': 'مرحبا بك في ريميكسا',
    'common.loading': 'جار التحميل...',
    'royalty.breakdown': 'تفصيل الإتاوات',
    'ledger.title': 'دفتر المعاملات',
    'c2pa.verified': 'تم التحقق من C2PA'
  }
};

// Translation context
interface TranslationContextType {
  language: string;
  setLanguage: (lang: string) => void;
  t: (key: string, fallback?: string) => string;
  isRTL: boolean;
}

const TranslationContext = createContext<TranslationContextType | undefined>(undefined);

export function TranslationProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<string>('en');
  const [isRTL, setIsRTL] = useState<boolean>(false);

  useEffect(() => {
    // Load saved language from localStorage
    const savedLang = localStorage.getItem('remixa_language');
    if (savedLang && SUPPORTED_LANGUAGES[savedLang as keyof typeof SUPPORTED_LANGUAGES]) {
      setLanguageState(savedLang);
      setIsRTL(SUPPORTED_LANGUAGES[savedLang as keyof typeof SUPPORTED_LANGUAGES].rtl);
    } else {
      // Detect browser language
      const browserLang = navigator.language.split('-')[0];
      if (SUPPORTED_LANGUAGES[browserLang as keyof typeof SUPPORTED_LANGUAGES]) {
        setLanguageState(browserLang);
        setIsRTL(SUPPORTED_LANGUAGES[browserLang as keyof typeof SUPPORTED_LANGUAGES].rtl);
      }
    }
  }, []);

  const setLanguage = (lang: string) => {
    if (SUPPORTED_LANGUAGES[lang as keyof typeof SUPPORTED_LANGUAGES]) {
      setLanguageState(lang);
      setIsRTL(SUPPORTED_LANGUAGES[lang as keyof typeof SUPPORTED_LANGUAGES].rtl);
      localStorage.setItem('remixa_language', lang);
      
      // Update HTML dir attribute for RTL
      document.documentElement.dir = SUPPORTED_LANGUAGES[lang as keyof typeof SUPPORTED_LANGUAGES].rtl ? 'rtl' : 'ltr';
    }
  };

  const t = (key: string, fallback?: string): string => {
    const langTranslations = translations[language] || translations.en;
    return langTranslations[key] || translations.en[key] || fallback || key;
  };

  return (
    <TranslationContext.Provider value={{ language, setLanguage, t, isRTL }}>
      {children}
    </TranslationContext.Provider>
  );
}

export function useTranslation() {
  const context = useContext(TranslationContext);
  if (!context) {
    throw new Error('useTranslation must be used within TranslationProvider');
  }
  return context;
}

// Language Selector Component
export function LanguageSelector({ className = '' }: { className?: string }) {
  const { language, setLanguage } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className={`relative ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 px-3 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
        </svg>
        <span className="text-sm font-medium">
          {SUPPORTED_LANGUAGES[language as keyof typeof SUPPORTED_LANGUAGES]?.nativeName || 'English'}
        </span>
        <svg className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 z-50 max-h-96 overflow-y-auto">
          {Object.entries(SUPPORTED_LANGUAGES).map(([code, lang]) => (
            <button
              key={code}
              onClick={() => {
                setLanguage(code);
                setIsOpen(false);
              }}
              className={`w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${
                language === code ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400' : ''
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm">{lang.nativeName}</span>
                {language === code && (
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </div>
              <span className="text-xs text-gray-500 dark:text-gray-400">{lang.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default TranslationProvider;
