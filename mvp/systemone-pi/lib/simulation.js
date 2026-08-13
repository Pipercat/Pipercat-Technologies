const crypto = require('crypto');
const { DeviceAdapter } = require('./adapter');
const { createDevice } = require('./device-model');
const { validateCapabilities, PROFILE_DEFINITIONS } = require('./capabilities');

const DEFAULTS = {
  light: { power: false, brightness: 50, colorTemperature: 300, color: '#FFD9A6' }, switch: { power: false, powerConsumption: 0, energy: 0 }, sensor: { value: 21.4, unit: '°C', sensorType: 'temperature', battery: 86 },
  thermostat: { temperature: 20.8, targetTemperature: 21, mode: 'auto', heating: false, humidity: 46, battery: 74 }, blind: { position: 50, tilt: 0, battery: 92 }
};

class SimulationAdapter extends DeviceAdapter {
  constructor() { super('simulation'); }
  async discover() { return { id: 'systemone-simulation', name: 'SystemONE Simulation', simulated: true }; }
  async pair() { return { paired: true, simulated: true }; }
  async listDevices(devices = []) { return devices.filter(device => device.integration === this.id); }
  create({ profile, name, roomId, id, manufacturer = 'SystemONE', model, serialNumber }) {
    if (!PROFILE_DEFINITIONS[profile]) throw Object.assign(new Error('Unbekanntes Geräteprofil.'), { code: 'DEVICE_PROFILE_INVALID' });
    return createDevice({ id: id || `sim-${profile}-${crypto.randomBytes(4).toString('hex')}`, integration: this.id, manufacturer, model: model || `Virtual ${profile}`, profile, name: String(name || PROFILE_DEFINITIONS[profile].label), roomId, compatibility: 'experimental', capabilities: DEFAULTS[profile], information: { firmwareVersion: 'sim-1.0', serialNumber: serialNumber || `SIM-${crypto.randomBytes(3).toString('hex').toUpperCase()}`, hardwareVersion: 'virtual' } });
  }
  async applyCapabilities(device, patch) { const values = validateCapabilities(device.profile, patch, { partial: true }); if (device.profile === 'thermostat' && Number.isFinite(values.targetTemperature)) values.heating = values.targetTemperature > device.capabilities.temperature; if (device.profile === 'switch' && typeof values.power === 'boolean') values.powerConsumption = values.power ? 42.5 : 0; return values; }
  async applyAction(device, action) { if (device.profile !== 'blind' || !['open','close','stop'].includes(action)) throw Object.assign(new Error('Geräteaktion wird nicht unterstützt.'), { code: 'DEVICE_ACTION_INVALID' }); if (action === 'stop') return {}; return { position: action === 'open' ? 100 : 0 }; }
}

module.exports = { SimulationAdapter, DEFAULTS };
