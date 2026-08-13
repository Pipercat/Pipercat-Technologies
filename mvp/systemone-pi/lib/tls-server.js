'use strict';
const fs=require('fs');
const https=require('https');
const path=require('path');
const {certificateStatus}=require('./tls-identity');
function tlsFailure(code,message,cause){return Object.assign(new Error(message),{code,cause})}
function createTlsServer({keyPath,certPath,requestHandler,readFileSync=fs.readFileSync,status=certificateStatus,createServer=https.createServer}={}){try{const identity=status(path.dirname(keyPath));if(identity.provisioned&&identity.revoked)throw tlsFailure('TLS_IDENTITY_REVOKED','Widerrufene TLS-Geräteidentität darf nicht starten.');const key=readFileSync(keyPath),cert=readFileSync(certPath);return createServer({key,cert,minVersion:'TLSv1.2'},requestHandler)}catch(error){if(error?.code==='TLS_IDENTITY_REVOKED')throw error;throw tlsFailure('TLS_MATERIAL_INVALID','TLS-Schlüssel, Zertifikat oder lokale Identitätsmetadaten sind ungültig oder nicht lesbar.',error)}}
function formatTlsStartupError(error){return `SystemONE-TLS-Startfehler [${error?.code||'TLS_MATERIAL_INVALID'}]: ${error?.message||'TLS-Initialisierung fehlgeschlagen.'}`}
module.exports={createTlsServer,formatTlsStartupError};
