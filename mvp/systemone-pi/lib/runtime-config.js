'use strict';

const fs=require('fs');
const {isPrivateIpv4}=require('./hue');

const BOOLEAN_KEYS=['CAMERA_MODULE_ENABLED','PIHOLE_MODULE_ENABLED','YOUDO_CALENDAR_ENABLED','YOUDO_TASKS_ENABLED'];
const MODE_KEYS=['HUE_MODE','CAMERA_MODE','PIHOLE_MODE','GOVEE_MODE'];
const EX_CONFIG=78;

function configError(code,message,field){return Object.assign(new Error(message),{code,details:{field}})}

function validateRuntimeConfig(env=process.env,{existsSync=fs.existsSync}={}){
  const port=env.PORT===undefined?4170:Number(env.PORT);
  if(!Number.isInteger(port)||port<1||port>65535)throw configError('CONFIG_PORT_INVALID','PORT muss eine ganze Zahl zwischen 1 und 65535 sein.','PORT');
  for(const key of BOOLEAN_KEYS)if(env[key]!==undefined&&!['true','false'].includes(env[key]))throw configError('CONFIG_BOOLEAN_INVALID',`${key} muss exakt true oder false sein.`,key);
  for(const key of MODE_KEYS)if(env[key]!==undefined&&!['simulation','real'].includes(env[key]))throw configError('CONFIG_MODE_INVALID',`${key} muss simulation oder real sein.`,key);
  if(env.GOVEE_MODE==='real')throw configError('GOVEE_HARDWARE_NOT_RELEASED','Realer Govee-Modus ist bis zur Hardwarefreigabe gesperrt.','GOVEE_MODE');
  if(env.HUE_BRIDGE_IP&&!isPrivateIpv4(env.HUE_BRIDGE_IP))throw configError('HUE_INVALID_BRIDGE_IP','HUE_BRIDGE_IP muss eine private lokale IPv4-Adresse sein.','HUE_BRIDGE_IP');
  const tlsKey=String(env.TLS_KEY_PATH||''),tlsCert=String(env.TLS_CERT_PATH||'');
  if(Boolean(tlsKey)!==Boolean(tlsCert))throw configError('TLS_CONFIG_INCOMPLETE','TLS_KEY_PATH und TLS_CERT_PATH müssen gemeinsam gesetzt sein.','TLS_KEY_PATH/TLS_CERT_PATH');
  for(const [field,file] of [['TLS_KEY_PATH',tlsKey],['TLS_CERT_PATH',tlsCert],['UPDATE_PUBLIC_KEY_PATH',String(env.UPDATE_PUBLIC_KEY_PATH||'')]])if(file&&!existsSync(file))throw configError('CONFIG_FILE_MISSING',`${field} verweist auf keine vorhandene Datei.`,field);
  return{port,tlsEnabled:Boolean(tlsKey&&tlsCert),tlsKeyPath:tlsKey||null,tlsCertPath:tlsCert||null,updatePublicKeyPath:env.UPDATE_PUBLIC_KEY_PATH||null};
}

function formatConfigError(error){return `SystemONE-Konfigurationsfehler [${error?.code||'CONFIG_INVALID'}]: ${error?.message||'Unbekannter Konfigurationsfehler.'}`}

module.exports={BOOLEAN_KEYS,MODE_KEYS,EX_CONFIG,validateRuntimeConfig,formatConfigError};
