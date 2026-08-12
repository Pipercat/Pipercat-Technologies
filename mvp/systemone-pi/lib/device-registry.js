const { EventEmitter } = require('events');
const { createDevice, publicDevice } = require('./device-model');
const { validateCapabilities } = require('./capabilities');

class DeviceRegistry extends EventEmitter {
  constructor(devices = []) { super(); this.devices = new Map(); devices.forEach(device => this.upsert(device, { silent: true })); }
  list({ publicOnly = false } = {}) { const values = [...this.devices.values()]; return publicOnly ? values.map(publicDevice) : values; }
  get(id) { return this.devices.get(id) || null; }
  upsert(input, { silent = false } = {}) { const device = createDevice(input); const existed = this.devices.has(device.id); this.devices.set(device.id, device); if (!silent) this.emit(existed ? 'device.updated' : 'device.added', publicDevice(device)); return device; }
  removeByIntegration(integration) { for (const [id, device] of this.devices) if (device.integration === integration) this.devices.delete(id); }
  replaceIntegration(integration, devices) { const preserved = this.list().filter(device => device.integration !== integration); this.devices.clear(); [...preserved, ...devices].forEach(device => this.upsert(device, { silent: true })); this.emit('registry.changed', { integration, count: devices.length }); }
  patch(id, patch) {
    const current = this.get(id); if (!current) return null;
    const next = { ...current, ...patch, diagnostics: { ...current.diagnostics, ...(patch.diagnostics || {}) } };
    if (patch.capabilities) next.capabilities = { ...current.capabilities, ...validateCapabilities(current.profile, patch.capabilities, { partial: true }) };
    return this.upsert(next);
  }
}

module.exports = { DeviceRegistry };
