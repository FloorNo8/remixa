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

// Translation keys. English is the canonical base; t() falls back to English for any
// missing key, so a partial dict never breaks the UI.
//
// ⚠️ The non-English strings below are a MACHINE-ASSISTED DRAFT and need professional
// native review before launch — especially the money/compliance keys (royalty.*, ledger.*,
// c2pa.*), where a mistranslation could misstate a financial guarantee. en is authoritative.
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
    'common.cancel': 'Cancelar',
    'common.save': 'Guardar',
    'common.delete': 'Eliminar',
    'common.edit': 'Editar',
    'common.create': 'Crear',
    'nav.dashboard': 'Panel',
    'nav.create': 'Crear',
    'nav.earnings': 'Ganancias',
    'nav.profile': 'Perfil',
    'nav.settings': 'Ajustes',
    'royalty.breakdown': 'Desglose de Regalías',
    'royalty.platform_fee': 'Tarifa de Plataforma',
    'royalty.parent_creator': 'Creador Original',
    'royalty.grandparent_creator': 'Creador de Segundo Nivel',
    'royalty.total': 'Total',
    'royalty.guaranteed': 'Garantía de Exactitud Monetaria',
    'royalty.conservation': 'Conservación Garantizada',
    'royalty.learn_more': 'Cómo funcionan las regalías',
    'ledger.title': 'Libro de Transacciones',
    'ledger.subtitle': 'Registro de auditoría inmutable de ingresos y pagos',
    'ledger.balance': 'Saldo Actual',
    'ledger.no_transactions': '¡Aún no hay transacciones. Crea remixes para ganar!',
    'ledger.append_only': 'Libro de Solo Anexión',
    'ledger.guarantee': 'Todas las transacciones son inmutables y verificadas criptográficamente.',
    'c2pa.verified': 'Verificado C2PA',
    'c2pa.credentials': 'Credenciales de Contenido',
    'c2pa.generator': 'Generador',
    'c2pa.parent': 'Generación Original',
    'c2pa.training': 'Datos de Entrenamiento de IA',
    'c2pa.manifest': 'Ver Manifiesto Completo',
    'c2pa.learn': 'Más información sobre C2PA',
    'advanced.multi_currency': 'Multidivisa',
    'advanced.dynamic_splits': 'Divisiones Personalizadas',
    'advanced.pools': 'Fondos de Colaboración',
    'advanced.blockchain': 'Blockchain',
    'advanced.instant_payouts': 'Pagos Instantáneos',
    'error.network': 'Error de red. Inténtalo de nuevo.',
    'error.unauthorized': 'No autorizado. Inicia sesión.',
    'error.not_found': 'No encontrado.',
    'error.server': 'Error del servidor. Inténtalo más tarde.'
  },
  
  fr: {
    'common.welcome': 'Bienvenue sur Remixa',
    'common.loading': 'Chargement...',
    'common.error': 'Erreur',
    'common.success': 'Succès',
    'common.cancel': 'Annuler',
    'common.save': 'Enregistrer',
    'common.delete': 'Supprimer',
    'common.edit': 'Modifier',
    'common.create': 'Créer',
    'nav.dashboard': 'Tableau de bord',
    'nav.create': 'Créer',
    'nav.earnings': 'Revenus',
    'nav.profile': 'Profil',
    'nav.settings': 'Paramètres',
    'royalty.breakdown': 'Répartition des Redevances',
    'royalty.platform_fee': 'Frais de Plateforme',
    'royalty.parent_creator': 'Créateur Original',
    'royalty.grandparent_creator': 'Créateur de Deuxième Niveau',
    'royalty.total': 'Total',
    'royalty.guaranteed': 'Garantie d\'Exactitude Monétaire',
    'royalty.conservation': 'Conservation Garantie',
    'royalty.learn_more': 'Comment fonctionnent les redevances',
    'ledger.title': 'Registre des Transactions',
    'ledger.subtitle': 'Piste d\'audit immuable de tous les revenus et paiements',
    'ledger.balance': 'Solde Actuel',
    'ledger.no_transactions': 'Aucune transaction pour le moment. Créez des remix pour gagner !',
    'ledger.append_only': 'Registre en Ajout Seul',
    'ledger.guarantee': 'Toutes les transactions sont immuables et vérifiées cryptographiquement.',
    'c2pa.verified': 'Vérifié C2PA',
    'c2pa.credentials': 'Identifiants de Contenu',
    'c2pa.generator': 'Générateur',
    'c2pa.parent': 'Génération Originale',
    'c2pa.training': 'Données d\'Entraînement IA',
    'c2pa.manifest': 'Voir le Manifeste Complet',
    'c2pa.learn': 'En savoir plus sur C2PA',
    'advanced.multi_currency': 'Multidevise',
    'advanced.dynamic_splits': 'Partages Personnalisés',
    'advanced.pools': 'Pools de Collaboration',
    'advanced.blockchain': 'Blockchain',
    'advanced.instant_payouts': 'Paiements Instantanés',
    'error.network': 'Erreur réseau. Veuillez réessayer.',
    'error.unauthorized': 'Non autorisé. Veuillez vous connecter.',
    'error.not_found': 'Introuvable.',
    'error.server': 'Erreur serveur. Veuillez réessayer plus tard.'
  },
  
  de: {
    'common.welcome': 'Willkommen bei Remixa',
    'common.loading': 'Laden...',
    'common.error': 'Fehler',
    'common.success': 'Erfolg',
    'common.cancel': 'Abbrechen',
    'common.save': 'Speichern',
    'common.delete': 'Löschen',
    'common.edit': 'Bearbeiten',
    'common.create': 'Erstellen',
    'nav.dashboard': 'Dashboard',
    'nav.create': 'Erstellen',
    'nav.earnings': 'Einnahmen',
    'nav.profile': 'Profil',
    'nav.settings': 'Einstellungen',
    'royalty.breakdown': 'Lizenzgebühren-Aufschlüsselung',
    'royalty.platform_fee': 'Plattformgebühr',
    'royalty.parent_creator': 'Ursprünglicher Ersteller',
    'royalty.grandparent_creator': 'Ersteller zweiter Ebene',
    'royalty.total': 'Gesamt',
    'royalty.guaranteed': 'Garantie der monetären Korrektheit',
    'royalty.conservation': 'Erhaltung garantiert',
    'royalty.learn_more': 'So funktionieren Lizenzgebühren',
    'ledger.title': 'Transaktionsbuch',
    'ledger.subtitle': 'Unveränderlicher Prüfpfad aller Einnahmen und Auszahlungen',
    'ledger.balance': 'Aktuelles Guthaben',
    'ledger.no_transactions': 'Noch keine Transaktionen. Erstelle Remixe, um zu verdienen!',
    'ledger.append_only': 'Nur-Anhängen-Buch',
    'ledger.guarantee': 'Alle Transaktionen sind unveränderlich und kryptografisch verifiziert.',
    'c2pa.verified': 'C2PA Verifiziert',
    'c2pa.credentials': 'Inhaltsnachweise',
    'c2pa.generator': 'Generator',
    'c2pa.parent': 'Ursprüngliche Generierung',
    'c2pa.training': 'KI-Trainingsdaten',
    'c2pa.manifest': 'Vollständiges Manifest anzeigen',
    'c2pa.learn': 'Mehr über C2PA erfahren',
    'advanced.multi_currency': 'Mehrere Währungen',
    'advanced.dynamic_splits': 'Individuelle Aufteilungen',
    'advanced.pools': 'Kollaborations-Pools',
    'advanced.blockchain': 'Blockchain',
    'advanced.instant_payouts': 'Sofortauszahlungen',
    'error.network': 'Netzwerkfehler. Bitte versuche es erneut.',
    'error.unauthorized': 'Nicht autorisiert. Bitte melde dich an.',
    'error.not_found': 'Nicht gefunden.',
    'error.server': 'Serverfehler. Bitte versuche es später erneut.'
  },
  
  ar: {
    'common.welcome': 'مرحبا بك في ريميكسا',
    'common.loading': 'جار التحميل...',
    'common.error': 'خطأ',
    'common.success': 'نجاح',
    'common.cancel': 'إلغاء',
    'common.save': 'حفظ',
    'common.delete': 'حذف',
    'common.edit': 'تعديل',
    'common.create': 'إنشاء',
    'nav.dashboard': 'لوحة التحكم',
    'nav.create': 'إنشاء',
    'nav.earnings': 'الأرباح',
    'nav.profile': 'الملف الشخصي',
    'nav.settings': 'الإعدادات',
    'royalty.breakdown': 'تفصيل الإتاوات',
    'royalty.platform_fee': 'رسوم المنصة',
    'royalty.parent_creator': 'المنشئ الأصلي',
    'royalty.grandparent_creator': 'منشئ المستوى الثاني',
    'royalty.total': 'الإجمالي',
    'royalty.guaranteed': 'ضمان الدقة المالية',
    'royalty.conservation': 'الحفظ مضمون',
    'royalty.learn_more': 'كيف تعمل الإتاوات',
    'ledger.title': 'دفتر المعاملات',
    'ledger.subtitle': 'سجل تدقيق غير قابل للتغيير لجميع الأرباح والمدفوعات',
    'ledger.balance': 'الرصيد الحالي',
    'ledger.no_transactions': 'لا توجد معاملات بعد. أنشئ ريمكسات لتربح!',
    'ledger.append_only': 'دفتر الإضافة فقط',
    'ledger.guarantee': 'جميع المعاملات غير قابلة للتغيير ومُتحقَّق منها تشفيريًا.',
    'c2pa.verified': 'تم التحقق من C2PA',
    'c2pa.credentials': 'بيانات اعتماد المحتوى',
    'c2pa.generator': 'المولّد',
    'c2pa.parent': 'التوليد الأصلي',
    'c2pa.training': 'بيانات تدريب الذكاء الاصطناعي',
    'c2pa.manifest': 'عرض البيان الكامل',
    'c2pa.learn': 'اعرف المزيد عن C2PA',
    'advanced.multi_currency': 'متعدد العملات',
    'advanced.dynamic_splits': 'تقسيمات مخصصة',
    'advanced.pools': 'مجمّعات التعاون',
    'advanced.blockchain': 'بلوكتشين',
    'advanced.instant_payouts': 'مدفوعات فورية',
    'error.network': 'خطأ في الشبكة. حاول مرة أخرى.',
    'error.unauthorized': 'غير مصرّح. يرجى تسجيل الدخول.',
    'error.not_found': 'غير موجود.',
    'error.server': 'خطأ في الخادم. حاول مرة أخرى لاحقًا.'
  },

  it: {
    'common.welcome': 'Benvenuto su Remixa',
    'common.loading': 'Caricamento...',
    'common.error': 'Errore',
    'common.success': 'Successo',
    'common.cancel': 'Annulla',
    'common.save': 'Salva',
    'common.delete': 'Elimina',
    'common.edit': 'Modifica',
    'common.create': 'Crea',
    'nav.dashboard': 'Dashboard',
    'nav.create': 'Crea',
    'nav.earnings': 'Guadagni',
    'nav.profile': 'Profilo',
    'nav.settings': 'Impostazioni',
    'royalty.breakdown': 'Ripartizione delle Royalty',
    'royalty.platform_fee': 'Commissione della Piattaforma',
    'royalty.parent_creator': 'Creatore Originale',
    'royalty.grandparent_creator': 'Creatore di Secondo Livello',
    'royalty.total': 'Totale',
    'royalty.guaranteed': 'Garanzia di Correttezza Monetaria',
    'royalty.conservation': 'Conservazione Garantita',
    'royalty.learn_more': 'Come funzionano le royalty',
    'ledger.title': 'Registro delle Transazioni',
    'ledger.subtitle': 'Traccia di controllo immutabile di tutti i guadagni e pagamenti',
    'ledger.balance': 'Saldo Attuale',
    'ledger.no_transactions': 'Ancora nessuna transazione. Crea remix per guadagnare!',
    'ledger.append_only': 'Registro a Sola Aggiunta',
    'ledger.guarantee': 'Tutte le transazioni sono immutabili e verificate crittograficamente.',
    'c2pa.verified': 'Verificato C2PA',
    'c2pa.credentials': 'Credenziali del Contenuto',
    'c2pa.generator': 'Generatore',
    'c2pa.parent': 'Generazione Originale',
    'c2pa.training': 'Dati di Addestramento IA',
    'c2pa.manifest': 'Visualizza Manifesto Completo',
    'c2pa.learn': 'Scopri di più su C2PA',
    'advanced.multi_currency': 'Multivaluta',
    'advanced.dynamic_splits': 'Divisioni Personalizzate',
    'advanced.pools': 'Pool di Collaborazione',
    'advanced.blockchain': 'Blockchain',
    'advanced.instant_payouts': 'Pagamenti Istantanei',
    'error.network': 'Errore di rete. Riprova.',
    'error.unauthorized': 'Non autorizzato. Effettua l\'accesso.',
    'error.not_found': 'Non trovato.',
    'error.server': 'Errore del server. Riprova più tardi.'
  },

  pt: {
    'common.welcome': 'Bem-vindo ao Remixa',
    'common.loading': 'Carregando...',
    'common.error': 'Erro',
    'common.success': 'Sucesso',
    'common.cancel': 'Cancelar',
    'common.save': 'Salvar',
    'common.delete': 'Excluir',
    'common.edit': 'Editar',
    'common.create': 'Criar',
    'nav.dashboard': 'Painel',
    'nav.create': 'Criar',
    'nav.earnings': 'Ganhos',
    'nav.profile': 'Perfil',
    'nav.settings': 'Configurações',
    'royalty.breakdown': 'Detalhamento de Royalties',
    'royalty.platform_fee': 'Taxa da Plataforma',
    'royalty.parent_creator': 'Criador Original',
    'royalty.grandparent_creator': 'Criador de Segundo Nível',
    'royalty.total': 'Total',
    'royalty.guaranteed': 'Garantia de Exatidão Monetária',
    'royalty.conservation': 'Conservação Garantida',
    'royalty.learn_more': 'Como funcionam os royalties',
    'ledger.title': 'Livro de Transações',
    'ledger.subtitle': 'Trilha de auditoria imutável de todos os ganhos e pagamentos',
    'ledger.balance': 'Saldo Atual',
    'ledger.no_transactions': 'Ainda não há transações. Crie remixes para ganhar!',
    'ledger.append_only': 'Livro Somente de Anexação',
    'ledger.guarantee': 'Todas as transações são imutáveis e verificadas criptograficamente.',
    'c2pa.verified': 'Verificado C2PA',
    'c2pa.credentials': 'Credenciais de Conteúdo',
    'c2pa.generator': 'Gerador',
    'c2pa.parent': 'Geração Original',
    'c2pa.training': 'Dados de Treinamento de IA',
    'c2pa.manifest': 'Ver Manifesto Completo',
    'c2pa.learn': 'Saiba mais sobre C2PA',
    'advanced.multi_currency': 'Multimoeda',
    'advanced.dynamic_splits': 'Divisões Personalizadas',
    'advanced.pools': 'Pools de Colaboração',
    'advanced.blockchain': 'Blockchain',
    'advanced.instant_payouts': 'Pagamentos Instantâneos',
    'error.network': 'Erro de rede. Tente novamente.',
    'error.unauthorized': 'Não autorizado. Faça login.',
    'error.not_found': 'Não encontrado.',
    'error.server': 'Erro do servidor. Tente novamente mais tarde.'
  },

  nl: {
    'common.welcome': 'Welkom bij Remixa',
    'common.loading': 'Laden...',
    'common.error': 'Fout',
    'common.success': 'Gelukt',
    'common.cancel': 'Annuleren',
    'common.save': 'Opslaan',
    'common.delete': 'Verwijderen',
    'common.edit': 'Bewerken',
    'common.create': 'Aanmaken',
    'nav.dashboard': 'Dashboard',
    'nav.create': 'Aanmaken',
    'nav.earnings': 'Inkomsten',
    'nav.profile': 'Profiel',
    'nav.settings': 'Instellingen',
    'royalty.breakdown': 'Royalty-uitsplitsing',
    'royalty.platform_fee': 'Platformkosten',
    'royalty.parent_creator': 'Oorspronkelijke Maker',
    'royalty.grandparent_creator': 'Maker op Tweede Niveau',
    'royalty.total': 'Totaal',
    'royalty.guaranteed': 'Garantie van Monetaire Juistheid',
    'royalty.conservation': 'Behoud Gegarandeerd',
    'royalty.learn_more': 'Hoe royalty\'s werken',
    'ledger.title': 'Transactieboek',
    'ledger.subtitle': 'Onveranderlijk controlespoor van alle inkomsten en uitbetalingen',
    'ledger.balance': 'Huidig Saldo',
    'ledger.no_transactions': 'Nog geen transacties. Maak remixes om te verdienen!',
    'ledger.append_only': 'Alleen-toevoegen Grootboek',
    'ledger.guarantee': 'Alle transacties zijn onveranderlijk en cryptografisch geverifieerd.',
    'c2pa.verified': 'C2PA Geverifieerd',
    'c2pa.credentials': 'Inhoudsreferenties',
    'c2pa.generator': 'Generator',
    'c2pa.parent': 'Oorspronkelijke Generatie',
    'c2pa.training': 'AI-trainingsgegevens',
    'c2pa.manifest': 'Volledig Manifest Bekijken',
    'c2pa.learn': 'Meer informatie over C2PA',
    'advanced.multi_currency': 'Meerdere Valuta\'s',
    'advanced.dynamic_splits': 'Aangepaste Verdelingen',
    'advanced.pools': 'Samenwerkingspools',
    'advanced.blockchain': 'Blockchain',
    'advanced.instant_payouts': 'Directe Uitbetalingen',
    'error.network': 'Netwerkfout. Probeer het opnieuw.',
    'error.unauthorized': 'Niet geautoriseerd. Log in.',
    'error.not_found': 'Niet gevonden.',
    'error.server': 'Serverfout. Probeer het later opnieuw.'
  },

  pl: {
    'common.welcome': 'Witamy w Remixa',
    'common.loading': 'Ładowanie...',
    'common.error': 'Błąd',
    'common.success': 'Sukces',
    'common.cancel': 'Anuluj',
    'common.save': 'Zapisz',
    'common.delete': 'Usuń',
    'common.edit': 'Edytuj',
    'common.create': 'Utwórz',
    'nav.dashboard': 'Panel',
    'nav.create': 'Utwórz',
    'nav.earnings': 'Zarobki',
    'nav.profile': 'Profil',
    'nav.settings': 'Ustawienia',
    'royalty.breakdown': 'Podział Tantiem',
    'royalty.platform_fee': 'Opłata Platformy',
    'royalty.parent_creator': 'Twórca Oryginału',
    'royalty.grandparent_creator': 'Twórca Drugiego Poziomu',
    'royalty.total': 'Razem',
    'royalty.guaranteed': 'Gwarancja Poprawności Finansowej',
    'royalty.conservation': 'Zachowanie Gwarantowane',
    'royalty.learn_more': 'Jak działają tantiemy',
    'ledger.title': 'Księga Transakcji',
    'ledger.subtitle': 'Niezmienny ślad audytowy wszystkich zarobków i wypłat',
    'ledger.balance': 'Aktualne Saldo',
    'ledger.no_transactions': 'Brak transakcji. Twórz remiksy, aby zarabiać!',
    'ledger.append_only': 'Księga Tylko do Dopisywania',
    'ledger.guarantee': 'Wszystkie transakcje są niezmienne i zweryfikowane kryptograficznie.',
    'c2pa.verified': 'Zweryfikowano C2PA',
    'c2pa.credentials': 'Poświadczenia Treści',
    'c2pa.generator': 'Generator',
    'c2pa.parent': 'Oryginalna Generacja',
    'c2pa.training': 'Dane Treningowe AI',
    'c2pa.manifest': 'Zobacz Pełny Manifest',
    'c2pa.learn': 'Dowiedz się więcej o C2PA',
    'advanced.multi_currency': 'Wiele Walut',
    'advanced.dynamic_splits': 'Niestandardowe Podziały',
    'advanced.pools': 'Pule Współpracy',
    'advanced.blockchain': 'Blockchain',
    'advanced.instant_payouts': 'Natychmiastowe Wypłaty',
    'error.network': 'Błąd sieci. Spróbuj ponownie.',
    'error.unauthorized': 'Brak autoryzacji. Zaloguj się.',
    'error.not_found': 'Nie znaleziono.',
    'error.server': 'Błąd serwera. Spróbuj ponownie później.'
  },

  ru: {
    'common.welcome': 'Добро пожаловать в Remixa',
    'common.loading': 'Загрузка...',
    'common.error': 'Ошибка',
    'common.success': 'Успешно',
    'common.cancel': 'Отмена',
    'common.save': 'Сохранить',
    'common.delete': 'Удалить',
    'common.edit': 'Редактировать',
    'common.create': 'Создать',
    'nav.dashboard': 'Панель',
    'nav.create': 'Создать',
    'nav.earnings': 'Доходы',
    'nav.profile': 'Профиль',
    'nav.settings': 'Настройки',
    'royalty.breakdown': 'Разбивка Роялти',
    'royalty.platform_fee': 'Комиссия Платформы',
    'royalty.parent_creator': 'Исходный Создатель',
    'royalty.grandparent_creator': 'Создатель Второго Уровня',
    'royalty.total': 'Итого',
    'royalty.guaranteed': 'Гарантия Финансовой Точности',
    'royalty.conservation': 'Сохранение Гарантировано',
    'royalty.learn_more': 'Как работают роялти',
    'ledger.title': 'Журнал Транзакций',
    'ledger.subtitle': 'Неизменяемый аудиторский след всех доходов и выплат',
    'ledger.balance': 'Текущий Баланс',
    'ledger.no_transactions': 'Пока нет транзакций. Создавайте ремиксы, чтобы зарабатывать!',
    'ledger.append_only': 'Журнал Только для Добавления',
    'ledger.guarantee': 'Все транзакции неизменяемы и криптографически проверены.',
    'c2pa.verified': 'Проверено C2PA',
    'c2pa.credentials': 'Учётные Данные Контента',
    'c2pa.generator': 'Генератор',
    'c2pa.parent': 'Исходная Генерация',
    'c2pa.training': 'Данные Обучения ИИ',
    'c2pa.manifest': 'Показать Полный Манифест',
    'c2pa.learn': 'Узнать больше о C2PA',
    'advanced.multi_currency': 'Мультивалютность',
    'advanced.dynamic_splits': 'Настраиваемые Разделения',
    'advanced.pools': 'Пулы Сотрудничества',
    'advanced.blockchain': 'Блокчейн',
    'advanced.instant_payouts': 'Мгновенные Выплаты',
    'error.network': 'Ошибка сети. Попробуйте снова.',
    'error.unauthorized': 'Не авторизован. Войдите в систему.',
    'error.not_found': 'Не найдено.',
    'error.server': 'Ошибка сервера. Попробуйте позже.'
  },

  ja: {
    'common.welcome': 'Remixaへようこそ',
    'common.loading': '読み込み中...',
    'common.error': 'エラー',
    'common.success': '成功',
    'common.cancel': 'キャンセル',
    'common.save': '保存',
    'common.delete': '削除',
    'common.edit': '編集',
    'common.create': '作成',
    'nav.dashboard': 'ダッシュボード',
    'nav.create': '作成',
    'nav.earnings': '収益',
    'nav.profile': 'プロフィール',
    'nav.settings': '設定',
    'royalty.breakdown': 'ロイヤリティの内訳',
    'royalty.platform_fee': 'プラットフォーム手数料',
    'royalty.parent_creator': '元のクリエイター',
    'royalty.grandparent_creator': '第2世代のクリエイター',
    'royalty.total': '合計',
    'royalty.guaranteed': '金額の正確性保証',
    'royalty.conservation': '保全保証',
    'royalty.learn_more': 'ロイヤリティの仕組み',
    'ledger.title': '取引台帳',
    'ledger.subtitle': 'すべての収益と支払いの不変の監査証跡',
    'ledger.balance': '現在の残高',
    'ledger.no_transactions': 'まだ取引がありません。リミックスを作成して収益を得ましょう！',
    'ledger.append_only': '追記専用台帳',
    'ledger.guarantee': 'すべての取引は不変であり、暗号的に検証されています。',
    'c2pa.verified': 'C2PA検証済み',
    'c2pa.credentials': 'コンテンツクレデンシャル',
    'c2pa.generator': 'ジェネレーター',
    'c2pa.parent': '元の生成',
    'c2pa.training': 'AIトレーニングデータ',
    'c2pa.manifest': '完全なマニフェストを表示',
    'c2pa.learn': 'C2PAについて詳しく見る',
    'advanced.multi_currency': '多通貨対応',
    'advanced.dynamic_splits': 'カスタム分割',
    'advanced.pools': 'コラボレーションプール',
    'advanced.blockchain': 'ブロックチェーン',
    'advanced.instant_payouts': '即時支払い',
    'error.network': 'ネットワークエラー。もう一度お試しください。',
    'error.unauthorized': '認証されていません。ログインしてください。',
    'error.not_found': '見つかりません。',
    'error.server': 'サーバーエラー。後でもう一度お試しください。'
  },

  zh: {
    'common.welcome': '欢迎来到 Remixa',
    'common.loading': '加载中...',
    'common.error': '错误',
    'common.success': '成功',
    'common.cancel': '取消',
    'common.save': '保存',
    'common.delete': '删除',
    'common.edit': '编辑',
    'common.create': '创建',
    'nav.dashboard': '仪表板',
    'nav.create': '创建',
    'nav.earnings': '收益',
    'nav.profile': '个人资料',
    'nav.settings': '设置',
    'royalty.breakdown': '版税明细',
    'royalty.platform_fee': '平台费用',
    'royalty.parent_creator': '原始创作者',
    'royalty.grandparent_creator': '第二级创作者',
    'royalty.total': '总计',
    'royalty.guaranteed': '金额准确性保证',
    'royalty.conservation': '守恒保证',
    'royalty.learn_more': '版税如何运作',
    'ledger.title': '交易账本',
    'ledger.subtitle': '所有收益和付款的不可变审计记录',
    'ledger.balance': '当前余额',
    'ledger.no_transactions': '暂无交易。创建混音即可赚取收益！',
    'ledger.append_only': '仅追加账本',
    'ledger.guarantee': '所有交易均不可变且经过加密验证。',
    'c2pa.verified': 'C2PA 已验证',
    'c2pa.credentials': '内容凭证',
    'c2pa.generator': '生成器',
    'c2pa.parent': '原始生成',
    'c2pa.training': 'AI 训练数据',
    'c2pa.manifest': '查看完整清单',
    'c2pa.learn': '了解更多关于 C2PA',
    'advanced.multi_currency': '多币种',
    'advanced.dynamic_splits': '自定义分成',
    'advanced.pools': '协作池',
    'advanced.blockchain': '区块链',
    'advanced.instant_payouts': '即时付款',
    'error.network': '网络错误。请重试。',
    'error.unauthorized': '未授权。请登录。',
    'error.not_found': '未找到。',
    'error.server': '服务器错误。请稍后重试。'
  },

  he: {
    'common.welcome': 'ברוכים הבאים ל-Remixa',
    'common.loading': 'טוען...',
    'common.error': 'שגיאה',
    'common.success': 'הצלחה',
    'common.cancel': 'ביטול',
    'common.save': 'שמירה',
    'common.delete': 'מחיקה',
    'common.edit': 'עריכה',
    'common.create': 'יצירה',
    'nav.dashboard': 'לוח בקרה',
    'nav.create': 'יצירה',
    'nav.earnings': 'רווחים',
    'nav.profile': 'פרופיל',
    'nav.settings': 'הגדרות',
    'royalty.breakdown': 'פירוט תמלוגים',
    'royalty.platform_fee': 'עמלת פלטפורמה',
    'royalty.parent_creator': 'היוצר המקורי',
    'royalty.grandparent_creator': 'יוצר רמה שנייה',
    'royalty.total': 'סך הכול',
    'royalty.guaranteed': 'ערבות לדיוק כספי',
    'royalty.conservation': 'שימור מובטח',
    'royalty.learn_more': 'איך תמלוגים עובדים',
    'ledger.title': 'יומן עסקאות',
    'ledger.subtitle': 'נתיב ביקורת בלתי ניתן לשינוי של כל הרווחים והתשלומים',
    'ledger.balance': 'יתרה נוכחית',
    'ledger.no_transactions': 'אין עדיין עסקאות. צרו רמיקסים כדי להרוויח!',
    'ledger.append_only': 'יומן הוספה בלבד',
    'ledger.guarantee': 'כל העסקאות בלתי ניתנות לשינוי ומאומתות קריפטוגרפית.',
    'c2pa.verified': 'מאומת C2PA',
    'c2pa.credentials': 'אישורי תוכן',
    'c2pa.generator': 'מחולל',
    'c2pa.parent': 'יצירה מקורית',
    'c2pa.training': 'נתוני אימון בינה מלאכותית',
    'c2pa.manifest': 'הצג מניפסט מלא',
    'c2pa.learn': 'מידע נוסף על C2PA',
    'advanced.multi_currency': 'רב-מטבעי',
    'advanced.dynamic_splits': 'חלוקות מותאמות',
    'advanced.pools': 'מאגרי שיתוף פעולה',
    'advanced.blockchain': 'בלוקצ\'יין',
    'advanced.instant_payouts': 'תשלומים מיידיים',
    'error.network': 'שגיאת רשת. נסו שוב.',
    'error.unauthorized': 'לא מורשה. אנא התחברו.',
    'error.not_found': 'לא נמצא.',
    'error.server': 'שגיאת שרת. נסו שוב מאוחר יותר.'
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
