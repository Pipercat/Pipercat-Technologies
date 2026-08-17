'use strict';
const fs=require('fs');
const https=require('https');
const path=require('path');
const crypto=require('crypto');
const {certificateStatus}=require('./tls-identity');
function tlsFailure(code,message,cause){return Object.assign(new Error(message),{code,cause})}
function validateKeyPermissions(stat){const mode=stat.mode&0o777;if(!(mode&0o400)||(mode&0o077)!==0)throw tlsFailure('TLS_KEY_PERMISSIONS','Privater TLS-Schlüssel muss nur für den Besitzer lesbar sein.');return mode}
function validateCertificateWindow(cert,{now=new Date(),Certificate=crypto.X509Certificate}={}){const parsed=new Certificate(cert),current=now.getTime(),from=Date.parse(parsed.validFrom),to=Date.parse(parsed.validTo);if(!Number.isFinite(from)||!Number.isFinite(to))throw tlsFailure('TLS_MATERIAL_INVALID','TLS-Zertifikat besitzt keinen gültigen Zeitraum.');if(current<from)throw tlsFailure('TLS_CERT_NOT_YET_VALID','TLS-Zertifikat ist noch nicht gültig.');if(current>to)throw tlsFailure('TLS_CERT_EXPIRED','TLS-Zertifikat ist abgelaufen und muss lokal erneuert werden.');return{validFrom:new Date(from).toISOString(),validTo:new Date(to).toISOString()}}
function createTlsServer({keyPath,certPath,requestHandler,readFileSync=fs.readFileSync,statSync=fs.statSync,status=certificateStatus,createServer=https.createServer,now=new Date(),Certificate=crypto.X509Certificate}={}){try{const identity=status(path.dirname(keyPath));if(identity.provisioned&&identity.revoked)throw tlsFailure('TLS_IDENTITY_REVOKED','Widerrufene TLS-Geräteidentität darf nicht starten.');validateKeyPermissions(statSync(keyPath));const key=readFileSync(keyPath),cert=readFileSync(certPath);validateCertificateWindow(cert,{now,Certificate});return createServer({key,cert,minVersion:'TLSv1.2'},requestHandler)}catch(error){if(/^TLS_(?:IDENTITY_REVOKED|KEY_PERMISSIONS|CERT_NOT_YET_VALID|CERT_EXPIRED)$/.test(error?.code||''))throw error;throw tlsFailure('TLS_MATERIAL_INVALID','TLS-Schlüssel, Zertifikat oder lokale Identitätsmetadaten sind ungültig oder nicht lesbar.',error)}}
function formatTlsStartupError(error){return `SystemONE-TLS-Startfehler [${error?.code||'TLS_MATERIAL_INVALID'}]: ${error?.message||'TLS-Initialisierung fehlgeschlagen.'}`}
module.exports={validateKeyPermissions,validateCertificateWindow,createTlsServer,formatTlsStartupError};
