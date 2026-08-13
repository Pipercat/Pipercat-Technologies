'use strict';

const {EX_CONFIG,validateRuntimeConfig,formatConfigError}=require('../lib/runtime-config');

try{
  const config=validateRuntimeConfig(process.env);
  console.log(`SystemONE-Konfiguration gültig · Port ${config.port} · TLS ${config.tlsEnabled?'aktiv':'Entwicklungs-HTTP'}`);
}catch(error){
  console.error(formatConfigError(error));
  process.exit(EX_CONFIG);
}
