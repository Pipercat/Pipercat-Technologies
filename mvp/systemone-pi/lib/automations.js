const crypto = require('crypto');
const { EventEmitter } = require('events');

const OPERATORS = new Set(['equals', 'notEquals', 'above', 'below']);

function automationError(message, details = {}) {
  return Object.assign(new Error(message), { code: 'AUTOMATION_INVALID', details });
}

function compare(actual, operator, expected) {
  if (operator === 'equals') return actual === expected;
  if (operator === 'notEquals') return actual !== expected;
  if (operator === 'above') return Number.isFinite(actual) && Number.isFinite(expected) && actual > expected;
  if (operator === 'below') return Number.isFinite(actual) && Number.isFinite(expected) && actual < expected;
  return false;
}

function validatePredicate(value, field = 'condition') {
  if (!value || typeof value !== 'object' || !value.deviceId || !value.capability || !OPERATORS.has(value.operator)) throw automationError(`${field} ist ungültig.`);
  if (!['string', 'number', 'boolean'].includes(typeof value.value)) throw automationError(`${field}-Wert ist ungültig.`);
  return { deviceId: String(value.deviceId), capability: String(value.capability), operator: value.operator, value: value.value };
}

function validateAutomation(input, registry) {
  if (!input || typeof input !== 'object') throw automationError('Automation fehlt.');
  const name = String(input.name || '').trim().slice(0, 80);
  if (!name) throw automationError('Name der Automation fehlt.');
  let trigger;
  if (input.trigger?.type === 'device') trigger = { type: 'device', ...validatePredicate(input.trigger, 'Trigger') };
  else if (input.trigger?.type === 'time') {
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(input.trigger.at || '')) throw automationError('Zeit-Trigger muss HH:MM enthalten.');
    trigger = { type: 'time', at: input.trigger.at };
  } else if (input.trigger?.type === 'sun') {
    if (!['sunrise', 'sunset'].includes(input.trigger.event) || !Number.isInteger(input.trigger.offsetMinutes) || Math.abs(input.trigger.offsetMinutes) > 720) throw automationError('Sonnen-Trigger ist ungültig.');
    trigger = { type: 'sun', event: input.trigger.event, offsetMinutes: input.trigger.offsetMinutes };
  } else throw automationError('Trigger-Typ wird nicht unterstützt.');
  const conditions = Array.isArray(input.conditions) ? input.conditions.map(value => validatePredicate(value)) : [];
  const actions = Array.isArray(input.actions) ? input.actions.map(action => {
    if (action?.type !== 'device' || !action.deviceId || !action.capabilities || typeof action.capabilities !== 'object') throw automationError('Geräteaktion ist ungültig.');
    return { type: 'device', deviceId: String(action.deviceId), capabilities: { ...action.capabilities } };
  }) : [];
  if (!actions.length || actions.length > 10 || conditions.length > 10) throw automationError('Automation benötigt 1 bis 10 Aktionen und höchstens 10 Bedingungen.');
  for (const id of [trigger.deviceId, ...conditions.map(x => x.deviceId), ...actions.map(x => x.deviceId)].filter(Boolean)) if (!registry.get(id)) throw automationError(`Gerät ${id} wurde nicht gefunden.`, { deviceId: id });
  return { id: input.id || `automation-${crypto.randomBytes(6).toString('hex')}`, name, enabled: input.enabled !== false, trigger, conditions, actions, lastRun: input.lastRun || null, lastError: input.lastError || null };
}

const TEMPLATES = Object.freeze([
  { id: 'sensor-light-on', name: 'Sensor schaltet Licht ein', description: 'Wenn ein Sensorwert den Grenzwert überschreitet, wird ein Licht eingeschaltet.', triggerProfiles: ['sensor'], actionProfiles: ['light', 'switch'] },
  { id: 'temperature-heating', name: 'Bei Kälte wärmer stellen', description: 'Wenn die Temperatur unter den Grenzwert fällt, wird die Zieltemperatur gesetzt.', triggerProfiles: ['sensor', 'thermostat'], actionProfiles: ['thermostat'] },
  { id: 'device-off', name: 'Gerät ausschalten', description: 'Wenn ein Gerät seinen definierten Zustand erreicht, wird Licht oder Schalter ausgeschaltet.', triggerProfiles: ['light', 'switch', 'sensor'], actionProfiles: ['light', 'switch'] },
  { id: 'time-device', name: 'Gerät zu einer Uhrzeit schalten', description: 'Schaltet ein lokales Licht oder einen Schalter täglich zu einer festen Uhrzeit.', triggerProfiles: [], actionProfiles: ['light', 'switch'] },
  { id: 'sun-device', name: 'Gerät bei Sonnenereignis schalten', description: 'Schaltet ein lokales Gerät relativ zu Sonnenauf- oder Sonnenuntergang.', triggerProfiles: [], actionProfiles: ['light', 'switch'] }
]);

function fromTemplate(id, input, registry) {
  const template = TEMPLATES.find(value => value.id === id);
  if (!template) throw automationError('Automationsvorlage wurde nicht gefunden.');
  const triggerDevice = input.triggerDeviceId ? registry.get(input.triggerDeviceId) : null, actionDevice = registry.get(input.actionDeviceId);
  if ((template.triggerProfiles.length && (!triggerDevice || !template.triggerProfiles.includes(triggerDevice.profile))) || !actionDevice || !template.actionProfiles.includes(actionDevice.profile)) throw automationError('Geräte passen nicht zur gewählten Vorlage.');
  if (id === 'time-device') return validateAutomation({ name: input.name || template.name, trigger: { type: 'time', at: input.at }, actions: [{ type: 'device', deviceId: actionDevice.id, capabilities: { power: input.power !== false } }] }, registry);
  if (id === 'sun-device') return validateAutomation({ name: input.name || template.name, trigger: { type: 'sun', event: input.event || 'sunset', offsetMinutes: Number.isInteger(input.offsetMinutes) ? input.offsetMinutes : 0 }, actions: [{ type: 'device', deviceId: actionDevice.id, capabilities: { power: input.power !== false } }] }, registry);
  const threshold = Number(input.threshold);
  if (id === 'sensor-light-on') return validateAutomation({ name: input.name || template.name, trigger: { type: 'device', deviceId: triggerDevice.id, capability: 'value', operator: 'above', value: Number.isFinite(threshold) ? threshold : 0 }, actions: [{ type: 'device', deviceId: actionDevice.id, capabilities: { power: true } }] }, registry);
  if (id === 'temperature-heating') return validateAutomation({ name: input.name || template.name, trigger: { type: 'device', deviceId: triggerDevice.id, capability: triggerDevice.profile === 'sensor' ? 'value' : 'temperature', operator: 'below', value: Number.isFinite(threshold) ? threshold : 20 }, actions: [{ type: 'device', deviceId: actionDevice.id, capabilities: { targetTemperature: Number.isFinite(Number(input.targetValue)) ? Number(input.targetValue) : 21 } }] }, registry);
  return validateAutomation({ name: input.name || template.name, trigger: { type: 'device', deviceId: triggerDevice.id, capability: input.triggerCapability || (triggerDevice.profile === 'sensor' ? 'value' : 'power'), operator: 'equals', value: input.triggerValue ?? true }, actions: [{ type: 'device', deviceId: actionDevice.id, capabilities: { power: false } }] }, registry);
}

class AutomationEngine extends EventEmitter {
  constructor({ registry, executeAction, automations = [] }) {
    super(); this.registry = registry; this.executeAction = executeAction; this.running = new Set();
    this.automations = automations.map(value => validateAutomation(value, registry));
  }
  list() { return this.automations.map(value => structuredClone(value)); }
  add(input) { const automation = validateAutomation(input, this.registry); this.automations.push(automation); this.emit('changed', this.list()); return structuredClone(automation); }
  addFromTemplate(id, input) { return this.add(fromTemplate(id, input, this.registry)); }
  setEnabled(id, enabled) { const item = this.automations.find(value => value.id === id); if (!item) return null; item.enabled = Boolean(enabled); this.emit('changed', this.list()); return structuredClone(item); }
  remove(id) { const before = this.automations.length; this.automations = this.automations.filter(value => value.id !== id); if (before !== this.automations.length) this.emit('changed', this.list()); return before !== this.automations.length; }
  matches(predicate) { const device = this.registry.get(predicate.deviceId); return Boolean(device && compare(device.capabilities[predicate.capability], predicate.operator, predicate.value)); }
  async handleDeviceChange(deviceId) {
    const results = [];
    for (const automation of this.automations) {
      if (!automation.enabled || automation.trigger.type !== 'device' || automation.trigger.deviceId !== deviceId || this.running.has(automation.id) || !this.matches(automation.trigger) || !automation.conditions.every(value => this.matches(value))) continue;
      this.running.add(automation.id);
      try {
        for (const action of automation.actions) await this.executeAction(action);
        automation.lastRun = new Date().toISOString(); automation.lastError = null; results.push({ id: automation.id, success: true });
      } catch (error) {
        automation.lastError = { code: error.code || 'AUTOMATION_ACTION_FAILED', message: error.message, timestamp: new Date().toISOString() };
        results.push({ id: automation.id, success: false, error: automation.lastError });
      } finally { this.running.delete(automation.id); this.emit('executed', structuredClone(automation)); }
    }
    if (results.length) this.emit('changed', this.list());
    return results;
  }
  async executeScheduled(id) {
    const automation = this.automations.find(value => value.id === id);
    if (!automation || !automation.enabled || this.running.has(id) || !automation.conditions.every(value => this.matches(value))) return { id, success: false, skipped: true };
    this.running.add(id);
    try {
      for (const action of automation.actions) await this.executeAction(action);
      automation.lastRun = new Date().toISOString(); automation.lastError = null; return { id, success: true };
    } catch (error) {
      automation.lastError = { code: error.code || 'AUTOMATION_ACTION_FAILED', message: error.message, timestamp: new Date().toISOString() };
      return { id, success: false, error: automation.lastError };
    } finally { this.running.delete(id); this.emit('executed', structuredClone(automation)); this.emit('changed', this.list()); }
  }
}

module.exports = { AutomationEngine, TEMPLATES, compare, validateAutomation, fromTemplate };
