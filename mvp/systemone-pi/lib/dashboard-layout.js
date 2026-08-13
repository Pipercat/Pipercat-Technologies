const WIDGET_IDS = Object.freeze(['online', 'offline', 'automations', 'backup']);
const SIZES = Object.freeze(['normal', 'wide']);
const QUICK_ACTIONS = Object.freeze(['devices', 'automations', 'backup']);
const DEFAULT_DASHBOARD = Object.freeze({ widgets: WIDGET_IDS.map(id => Object.freeze({ id, visible: true, size: 'normal' })), quickAction: 'devices' });

function dashboardError(message) { return Object.assign(new Error(message), { code: 'DASHBOARD_LAYOUT_INVALID' }); }
function defaultDashboard() { return { widgets: DEFAULT_DASHBOARD.widgets.map(widget => ({ ...widget })), quickAction: DEFAULT_DASHBOARD.quickAction }; }
function validateDashboard(input) {
  if (!input || !Array.isArray(input.widgets) || input.widgets.length !== WIDGET_IDS.length) throw dashboardError('Dashboard muss alle vier Kernkarten enthalten.');
  const ids = input.widgets.map(widget => widget?.id);
  if (new Set(ids).size !== WIDGET_IDS.length || WIDGET_IDS.some(id => !ids.includes(id))) throw dashboardError('Dashboard enthält fehlende oder doppelte Karten.');
  const widgets = input.widgets.map(widget => {
    if (typeof widget.visible !== 'boolean' || !SIZES.includes(widget.size)) throw dashboardError('Sichtbarkeit oder Kartengröße ist ungültig.');
    return { id: widget.id, visible: widget.visible, size: widget.size };
  });
  if (!widgets.some(widget => widget.visible)) throw dashboardError('Mindestens eine Dashboard-Karte muss sichtbar bleiben.');
  if (widgets.filter(widget => widget.visible && widget.size === 'wide').length > 2) throw dashboardError('Höchstens zwei breite Karten sind erlaubt.');
  if (!QUICK_ACTIONS.includes(input.quickAction)) throw dashboardError('Schnellzugriff ist ungültig.');
  return { widgets, quickAction: input.quickAction };
}
function migrateDashboard(input) { try { return validateDashboard(input); } catch { return defaultDashboard(); } }

module.exports = { WIDGET_IDS, SIZES, QUICK_ACTIONS, DEFAULT_DASHBOARD, defaultDashboard, validateDashboard, migrateDashboard };
