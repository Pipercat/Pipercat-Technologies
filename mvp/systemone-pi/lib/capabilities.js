const PROFILE_DEFINITIONS = Object.freeze({
  light: { label: 'Licht', capabilities: { power: 'boolean', brightness: 'percentage' } },
  switch: { label: 'Steckdose / Schalter', capabilities: { power: 'boolean' } },
  sensor: { label: 'Sensor', capabilities: { value: 'number', unit: 'string' } },
  thermostat: { label: 'Heizung / Thermostat', capabilities: { temperature: 'temperature', targetTemperature: 'temperature' } },
  blind: { label: 'Rollladen / Jalousie', capabilities: { position: 'percentage' } }
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
  if (!Number.isFinite(value)) throw capabilityError(`${name} muss eine Zahl sein.`, { capability: name });
  if (kind === 'percentage') return Math.max(0, Math.min(100, Math.round(value)));
  if (kind === 'temperature') return Math.max(-50, Math.min(100, Math.round(value * 10) / 10));
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
    for (const name of Object.keys(definition.capabilities)) {
      if (!(name in normalized)) throw capabilityError(`Capability ${name} fehlt für Profil ${profile}.`, { profile, capability: name });
    }
  }
  return normalized;
}

function publicProfiles() {
  return Object.fromEntries(Object.entries(PROFILE_DEFINITIONS).map(([id, value]) => [id, { label: value.label, capabilities: Object.keys(value.capabilities) }]));
}

module.exports = { PROFILE_DEFINITIONS, validateCapabilities, publicProfiles };
