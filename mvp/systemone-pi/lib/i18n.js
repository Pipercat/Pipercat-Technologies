const SUPPORTED_LOCALES = Object.freeze({
  de: { id: 'de', label: 'Deutsch', nativeLabel: 'Deutsch', complete: true },
  en: { id: 'en', label: 'English', nativeLabel: 'English', complete: false }
});
const DEFAULT_LOCALE = 'de';

const MESSAGES = Object.freeze({
  de: { homeTitle: 'Home', homeSubtitle: 'Dein Zuhause ist bereit.', roomsTitle: 'Räume & Geräte', moreTitle: 'Mehr', localConnected: 'Lokal verbunden' },
  en: { homeTitle: 'Home', homeSubtitle: 'Your home is ready.', roomsTitle: 'Rooms & devices', moreTitle: 'More', localConnected: 'Connected locally' }
});

function validateLocale(locale) {
  const normalized = String(locale || '').trim().toLowerCase().split('-')[0];
  if (!SUPPORTED_LOCALES[normalized]) throw Object.assign(new Error('Sprache wird nicht unterstützt.'), { code: 'LOCALE_INVALID', details: { locale } });
  return normalized;
}

function localeCatalog() { return { defaultLocale: DEFAULT_LOCALE, locales: Object.values(SUPPORTED_LOCALES).map(item => ({ ...item })) }; }

function messagesFor(locale) { const selected = validateLocale(locale); return { locale: selected, fallbackLocale: DEFAULT_LOCALE, messages: { ...MESSAGES[DEFAULT_LOCALE], ...(MESSAGES[selected] || {}) } }; }

module.exports = { SUPPORTED_LOCALES, DEFAULT_LOCALE, validateLocale, localeCatalog, messagesFor };
