const { validateCapabilities } = require('./capabilities');

const COMPATIBILITY = new Set(['certified', 'compatible', 'experimental', 'unsupported']);
const AVAILABILITY = new Set(['online', 'offline', 'degraded', 'unknown']);

function requiredText(value, field) {
  const text = String(value || '').trim();
  if (!text) throw Object.assign(new Error(`${field} fehlt.`), { code: 'DEVICE_MODEL_INVALID', details: { field } });
  return text.slice(0, 100);
}

function createDevice(input) {
  const online = input.online !== false;
  const availability = input.availability || (online ? 'online' : 'offline');
  const compatibility = input.compatibility || 'experimental';
  if (!AVAILABILITY.has(availability) || !COMPATIBILITY.has(compatibility)) throw Object.assign(new Error('Gerätestatus ist ungültig.'), { code: 'DEVICE_MODEL_INVALID' });
  return {
    id: requiredText(input.id, 'id'),
    integration: requiredText(input.integration, 'integration'),
    manufacturer: requiredText(input.manufacturer || 'Unbekannt', 'manufacturer'),
    model: requiredText(input.model || 'Unbekannt', 'model'),
    profile: requiredText(input.profile, 'profile'),
    name: requiredText(input.name, 'name').slice(0, 60),
    roomId: input.roomId ? String(input.roomId).slice(0, 80) : null,
    online,
    availability,
    compatibility,
    capabilities: validateCapabilities(input.profile, input.capabilities),
    diagnostics: {
      lastSeen: input.diagnostics?.lastSeen || (online ? new Date().toISOString() : null),
      lastError: input.diagnostics?.lastError || null
    },
    information: {
      firmwareVersion: input.information?.firmwareVersion || null,
      serialNumber: input.information?.serialNumber || null,
      hardwareVersion: input.information?.hardwareVersion || null
    },
    adapterData: input.adapterData && typeof input.adapterData === 'object' ? { ...input.adapterData } : {}
  };
}

function migrateLegacyDevice(device) {
  if (device.profile && device.capabilities) return createDevice(device);
  const profile = device.type || 'switch';
  const capabilities = {};
  if (profile === 'light') Object.assign(capabilities, { power: Boolean(device.on), brightness: Number.isFinite(device.brightness) ? device.brightness : 50 });
  if (profile === 'switch') capabilities.power = Boolean(device.on);
  if (profile === 'sensor') Object.assign(capabilities, { value: Number.isFinite(device.value) ? device.value : 0, unit: device.unit || '–' });
  if (profile === 'thermostat') Object.assign(capabilities, { temperature: Number.isFinite(device.temperature) ? device.temperature : 20, targetTemperature: Number.isFinite(device.targetTemperature) ? device.targetTemperature : 21 });
  if (profile === 'blind') capabilities.position = Number.isFinite(device.position) ? device.position : 50;
  return createDevice({ ...device, profile, capabilities, manufacturer: device.integration === 'hue' ? 'Philips' : 'SystemONE', model: device.integration === 'hue' ? 'Hue Light' : `Virtual ${profile}`, compatibility: device.integration === 'hue' ? 'certified' : 'experimental', adapterData: { ...(device.adapterData || {}), hueId: device.hueId } });
}

function publicDevice(device) {
  const { adapterData, ...safe } = device;
  return safe;
}

module.exports = { createDevice, migrateLegacyDevice, publicDevice };
