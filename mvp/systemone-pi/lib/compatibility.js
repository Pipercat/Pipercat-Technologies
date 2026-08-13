const LEVELS = Object.freeze({
  certified: { label: 'SystemONE Certified', support: 'Vollständig getestet und für den normalen Einrichtungsablauf freigegeben.' },
  compatible: { label: 'SystemONE Compatible', support: 'Kernfunktionen getestet; Einschränkungen werden pro Modell dokumentiert.' },
  experimental: { label: 'Experimentell / Beta', support: 'Nur nach bewusster Aktivierung und ohne vollständige Funktionsgarantie.' },
  unsupported: { label: 'Nicht unterstützt', support: 'Nicht im normalen Einrichtungsablauf verfügbar.' }
});

const CATALOG = Object.freeze([
  { integration: 'simulation', manufacturer: 'SystemONE', category: 'development', profiles: ['light', 'switch', 'sensor', 'thermostat', 'blind'], level: 'experimental', localOnly: true, pilot: true, evidence: '50+ hardwarefreie Core-Selftests', limitations: ['Keine Aussage über reale Funk- oder Herstellerhardware'] },
  { integration: 'hue', manufacturer: 'Philips Hue', category: 'bridge', profiles: ['light'], level: 'experimental', localOnly: true, pilot: true, evidence: 'Adapter und Fehlermatrix hardwarefrei getestet', limitations: ['Physische Bridge- und Modellfreigabe ausstehend', 'Keine Hue-Cloud'] },
  { integration: 'govee', manufacturer: 'Govee', category: 'lan', profiles: ['light'], level: 'unsupported', localOnly: true, pilot: false, evidence: 'Noch nicht implementiert', limitations: ['Nur ausdrücklich lokal steuerbare Modelle vorgesehen'] },
  { integration: 'matter', manufacturer: 'Matter', category: 'standard', profiles: ['light', 'switch', 'sensor', 'thermostat', 'blind'], level: 'unsupported', localOnly: true, pilot: false, evidence: 'Eigener Testpfad erforderlich', limitations: ['Controller- und Modellmatrix offen'] },
  { integration: 'shelly', manufacturer: 'Shelly', category: 'lan', profiles: ['light', 'switch', 'sensor'], level: 'unsupported', localOnly: true, pilot: false, evidence: 'Eigener Testpfad erforderlich', limitations: ['Modell- und Firmwarematrix offen'] },
  { integration: 'zigbee', manufacturer: 'Zigbee', category: 'radio', profiles: ['light', 'switch', 'sensor', 'thermostat', 'blind'], level: 'unsupported', localOnly: true, pilot: false, evidence: 'Freigegebener Stick und eigener Testpfad erforderlich', limitations: ['Koordinator, Firmware und Modellmatrix offen'] },
  { integration: 'ikea', manufacturer: 'IKEA Home smart', category: 'zigbee', profiles: ['light', 'switch', 'sensor', 'blind'], level: 'unsupported', localOnly: true, pilot: false, evidence: 'Nur über später freigegebenen Zigbee-Pfad', limitations: ['Keine Modellfreigabe vorhanden'] }
]);

function publicCompatibilityCatalog() {
  return { levels: LEVELS, entries: CATALOG.map(entry => ({ ...entry, profiles: [...entry.profiles], limitations: [...entry.limitations] })) };
}

function compatibilityFor(integration) {
  return CATALOG.find(entry => entry.integration === integration) || null;
}

module.exports = { LEVELS, CATALOG, publicCompatibilityCatalog, compatibilityFor };
