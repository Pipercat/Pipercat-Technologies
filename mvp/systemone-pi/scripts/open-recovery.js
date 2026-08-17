#!/usr/bin/env node
const path=require('path');
const {RecoveryManager}=require('../lib/recovery-manager');
const dataDir=process.env.SYSTEMONE_DATA_DIR||path.join(__dirname,'../data');
try{const status=new RecoveryManager(dataDir).open();console.log(`SystemONE-Recovery lokal geöffnet bis ${status.expiresAt}. Browserzugriff im selben Heimnetz ist jetzt mit dem getrennt verwahrten Einmalcode möglich.`)}catch(error){console.error(`[${error.code||'RECOVERY_OPEN_FAILED'}] ${error.message}`);process.exitCode=1}
