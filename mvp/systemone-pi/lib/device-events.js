const DEVICE_EVENT_TYPES = Object.freeze(['device.added', 'device.updated', 'devices.resync']);

function normalizedDeviceEvent(type, payload, sequence, now = new Date()) {
  if (!DEVICE_EVENT_TYPES.includes(type)) throw Object.assign(new Error('Unbekannter Geräteereignistyp.'), { code: 'DEVICE_EVENT_INVALID' });
  const event = { schemaVersion: 1, sequence, type, timestamp: now.toISOString() };
  if (type === 'devices.resync') return { ...event, resync: true };
  return { ...event, device: {
    id: payload.id, profile: payload.profile, name: payload.name, roomId: payload.roomId || null,
    online: payload.online !== false, availability: payload.availability,
    capabilities: structuredClone(payload.capabilities || {}), diagnostics: structuredClone(payload.diagnostics || {})
  } };
}

module.exports = { DEVICE_EVENT_TYPES, normalizedDeviceEvent };
