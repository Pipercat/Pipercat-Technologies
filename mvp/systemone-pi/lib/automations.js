const crypto = require('crypto');
const { EventEmitter } = require('events');
const { sanitize } = require('./diagnostics');

const OPERATORS = new Set(['equals', 'notEquals', 'above', 'below']);

function automationError(message, details = {}) {
  return Object.assign(new Error(message), { code: 'AUTOMATION_INVALID', details });
}
function redactErrorMessage(value) { return String(value || 'Aktion fehlgeschlagen.').replace(/(token|secret|username|password|credential)\s*[=:]\s*[^\s,;]+/gi,'$1=[REDACTED]').replace(/\/api\/[^/\s]+\//g,'/api/[REDACTED]/'); }

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

function builderOptions(registry) {
  return registry.list({ publicOnly: true }).map(device => ({ id: device.id, name: device.name, profile: device.profile,
    fields: Object.entries(device.capabilities).filter(([, value]) => ['string','number','boolean'].includes(typeof value)).map(([capability, value]) => ({ capability, valueType: typeof value, operators: typeof value === 'number' ? ['above','below','equals','notEquals'] : ['equals','notEquals'] })),
    actions: device.profile === 'thermostat' ? ['targetTemperature'] : device.profile === 'blind' ? ['position'] : ['power']
  }));
}

class AutomationEngine extends EventEmitter {
  constructor({ registry, executeAction, automations = [], history = [], historyLimit = 100 }) {
    super(); this.registry = registry; this.executeAction = executeAction; this.running = new Set();
    this.automations = automations.map(value => validateAutomation(value, registry));
    this.historyLimit = historyLimit; this.history = Array.isArray(history) ? history.slice(0, historyLimit) : [];
  }
  list() { return this.automations.map(value => structuredClone(value)); }
  listHistory() { return structuredClone(this.history); }
  recordExecution(automation, result) { const entry = { id: `execution-${crypto.randomBytes(6).toString('hex')}`, automationId: automation.id, automationName: automation.name, timestamp: new Date().toISOString(), ...result }; this.history.unshift(entry); this.history = this.history.slice(0, this.historyLimit); this.emit('history.changed', this.listHistory()); return entry; }
  async runActions(automation, { startIndex = 0, source = 'trigger', retryOf = null } = {}) { let completedActionCount = startIndex; try { for (let index=startIndex;index<automation.actions.length;index++) { await this.executeAction(automation.actions[index]); completedActionCount=index+1; } automation.lastRun=new Date().toISOString();automation.lastError=null;return this.recordExecution(automation,{success:true,source,retryOf,completedActionCount,totalActions:automation.actions.length}); } catch(error) { automation.lastError={code:error.code||'AUTOMATION_ACTION_FAILED',message:redactErrorMessage(error.message),timestamp:new Date().toISOString()};return this.recordExecution(automation,{success:false,source,retryOf,completedActionCount,totalActions:automation.actions.length,error:sanitize(automation.lastError)}); } }
  async retry(executionId) { const previous=this.history.find(item=>item.id===executionId);if(!previous||previous.success)throw automationError('Nur eine fehlgeschlagene Ausführung kann wiederholt werden.');if(previous.retriedBy)throw automationError('Diese Ausführung wurde bereits wiederholt.');const automation=this.automations.find(item=>item.id===previous.automationId);if(!automation)throw automationError('Automation für die Wiederholung wurde nicht gefunden.');if(this.running.has(automation.id))throw automationError('Automation wird bereits ausgeführt.');this.running.add(automation.id);try{const result=await this.runActions(automation,{startIndex:previous.completedActionCount,source:'retry',retryOf:previous.id});previous.retriedBy=result.id;this.emit('history.changed',this.listHistory());this.emit('changed',this.list());return structuredClone(result)}finally{this.running.delete(automation.id)}}
  add(input) { const automation = validateAutomation(input, this.registry); this.automations.push(automation); this.emit('changed', this.list()); return structuredClone(automation); }
  addFromTemplate(id, input) {
    const draft = fromTemplate(id, input, this.registry);
    if (input.secondActionDeviceId) {
      const target = this.registry.get(input.secondActionDeviceId);
      if (!target) throw automationError('Zweites Aktionsgerät wurde nicht gefunden.');
      const firstCapabilities = draft.actions[0].capabilities;
      const capabilities = target.profile === 'thermostat' ? { targetTemperature: Number(input.secondActionValue || 21) } : target.profile === 'blind' ? { position: Number(input.secondActionValue || 100) } : { power: firstCapabilities.power !== false };
      draft.actions.push({ type: 'device', deviceId: target.id, capabilities });
    }
    if (input.conditionDeviceId) draft.conditions.push(validatePredicate({ deviceId: input.conditionDeviceId, capability: input.conditionCapability, operator: input.conditionOperator, value: input.conditionValue }, 'Bedingung'));
    return this.add(draft);
  }
  setEnabled(id, enabled) { const item = this.automations.find(value => value.id === id); if (!item) return null; item.enabled = Boolean(enabled); this.emit('changed', this.list()); return structuredClone(item); }
  remove(id) { const before = this.automations.length; this.automations = this.automations.filter(value => value.id !== id); if (before !== this.automations.length) this.emit('changed', this.list()); return before !== this.automations.length; }
  matches(predicate) { const device = this.registry.get(predicate.deviceId); return Boolean(device && compare(device.capabilities[predicate.capability], predicate.operator, predicate.value)); }
  async handleDeviceChange(deviceId) {
    const results = [];
    for (const automation of this.automations) {
      if (!automation.enabled || automation.trigger.type !== 'device' || automation.trigger.deviceId !== deviceId || this.running.has(automation.id) || !this.matches(automation.trigger) || !automation.conditions.every(value => this.matches(value))) continue;
      this.running.add(automation.id);
      try { const execution=await this.runActions(automation);results.push({id:automation.id,success:execution.success,error:execution.error}); }
      finally { this.running.delete(automation.id); this.emit('executed', structuredClone(automation)); }
    }
    if (results.length) this.emit('changed', this.list());
    return results;
  }
  async executeScheduled(id) {
    const automation = this.automations.find(value => value.id === id);
    if (!automation || !automation.enabled || this.running.has(id) || !automation.conditions.every(value => this.matches(value))) return { id, success: false, skipped: true };
    this.running.add(id);
    try { const execution=await this.runActions(automation,{source:'scheduler'});return {id,success:execution.success,error:execution.error}; }
    finally { this.running.delete(id); this.emit('executed', structuredClone(automation)); this.emit('changed', this.list()); }
  }
}

module.exports = { AutomationEngine, TEMPLATES, compare, validateAutomation, fromTemplate, builderOptions };
