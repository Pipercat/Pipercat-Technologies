const crypto = require('crypto');
const { DeviceAdapter } = require('./adapter');
const { createDevice } = require('./device-model');
const { validateCapabilities, PROFILE_DEFINITIONS } = require('./capabilities');

const DEFAULTS = {
  light: { power: false, brightness: 50 }, switch: { power: false }, sensor: { value: 21.4, unit: '°C' },
  thermostat: { temperature: 20.8, targetTemperature: 21 }, blind: { position: 50 }
};

class SimulationAdapter extends DeviceAdapter {
  constructor() { super('simulation'); }
  async discover() { return { id: 'systemone-simulation', name: 'SystemONE Simulation', simulated: true }; }
  async pair() { return { paired: true, simulated: true }; }
  async listDevices(devices = []) { return devices.filter(device => device.integration === this.id); }
  create({ profile, name, roomId }) {
    if (!PROFILE_DEFINITIONS[profile]) throw Object.assign(new Error('Unbekanntes Geräteprofil.'), { code: 'DEVICE_PROFILE_INVALID' });
    return createDevice({ id: `sim-${profile}-${crypto.randomBytes(4).toString('hex')}`, integration: this.id, manufacturer: 'SystemONE', model: `Virtual ${profile}`, profile, name: String(name || PROFILE_DEFINITIONS[profile].label), roomId, compatibility: 'experimental', capabilities: DEFAULTS[profile] });
  }
  async applyCapabilities(device, patch) { return validateCapabilities(device.profile, patch, { partial: true }); }
}

module.exports = { SimulationAdapter, DEFAULTS };
