const THEMES = Object.freeze({
  Clear: { id: 'Clear', label: 'Clear', description: 'Hell, ruhig und einsteigerfreundlich.', available: true },
  Midnight: { id: 'Midnight', label: 'Midnight', description: 'Dunkel und für Displays optimiert.', available: true },
  Compact: { id: 'Compact', label: 'Compact', description: 'Informationsdicht und weiterhin touchfreundlich.', available: true },
  Living: { id: 'Living', label: 'Living', description: 'Weich und wohnlich.', available: false }
});
function validateTheme(value) { const theme = THEMES[value]; if (!theme || !theme.available) throw Object.assign(new Error('Theme ist noch nicht verfügbar.'), { code: 'THEME_INVALID', details: { theme: value } }); return theme.id; }
module.exports = { THEMES, validateTheme };
