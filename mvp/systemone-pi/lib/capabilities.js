const PROFILE_DEFINITIONS = Object.freeze({
  light: { label: 'Licht', required: ['power','brightness'], capabilities: { power: 'boolean', brightness: 'percentage', colorTemperature: 'colorTemperature', color: 'color', battery: 'percentage' } },
  switch: { label: 'Steckdose / Schalter', required: ['power'], capabilities: { power: 'boolean', powerConsumption: 'number', energy: 'number', battery: 'percentage' } },
  sensor: { label: 'Sensor', required: ['value','unit'], capabilities: { value: 'number', unit: 'string', sensorType: 'string', battery: 'percentage' } },
  thermostat: { label: 'Heizung / Thermostat', required: ['temperature','targetTemperature'], capabilities: { temperature: 'temperature', targetTemperature: 'temperature', mode: 'string', heating: 'boolean', humidity: 'percentage', battery: 'percentage' } },
  blind: { label: 'Rollladen / Jalousie', required: ['position'], capabilities: { position: 'percentage', tilt: 'percentage', battery: 'percentage' } }
});

function capabilityError(message, details = {}) {
  return Object.assign(new Error(message), { code: 'CAPABILITY_INVALID', details });
}

function normalizeValue(kind, value, name) {
  if (kind === 'boolean') {
    if (typeof value !== 'boolean') throw capabilityError(`${name} muss ein Wahrheitswert sein.`, { capability: name });
    return value;
  }
  if (kind === 'string') {
    if (typeof value !== 'string' || !value.trim()) throw capabilityError(`${name} muss Text enthalten.`, { capability: name });
    return value.trim().slice(0, 30);
  }
  if (kind === 'color') {
    if (typeof value !== 'string' || !/^#[0-9a-f]{6}$/i.test(value)) throw capabilityError(`${name} muss eine Hex-Farbe sein.`, { capability: name });
    return value.toUpperCase();
  }
  if (!Number.isFinite(value)) throw capabilityError(`${name} muss eine Zahl sein.`, { capability: name });
  if (kind === 'percentage') return Math.max(0, Math.min(100, Math.round(value)));
  if (kind === 'temperature') return Math.max(-50, Math.min(100, Math.round(value * 10) / 10));
  if (kind === 'colorTemperature') return Math.max(153, Math.min(500, Math.round(value)));
  return value;
}

function validateCapabilities(profile, values, { partial = false } = {}) {
  const definition = PROFILE_DEFINITIONS[profile];
  if (!definition) throw Object.assign(new Error('Unbekanntes Geräteprofil.'), { code: 'DEVICE_PROFILE_INVALID', details: { profile } });
  if (!values || typeof values !== 'object' || Array.isArray(values)) throw capabilityError('Capabilities müssen ein Objekt sein.');
  const normalized = {};
  for (const [name, value] of Object.entries(values)) {
    const kind = definition.capabilities[name];
    if (!kind) throw capabilityError(`Capability ${name} gehört nicht zum Profil ${profile}.`, { profile, capability: name });
    normalized[name] = normalizeValue(kind, value, name);
  }
  if (!partial) {
    for (const name of definition.required) {
      if (!(name in normalized)) throw capabilityError(`Capability ${name} fehlt für Profil ${profile}.`, { profile, capability: name });
    }
  }
  return normalized;
}

function publicProfiles() {
  return Object.fromEntries(Object.entries(PROFILE_DEFINITIONS).map(([id, value]) => [id, { label: value.label, capabilities: Object.keys(value.capabilities) }]));
}

module.exports = { PROFILE_DEFINITIONS, validateCapabilities, publicProfiles };
