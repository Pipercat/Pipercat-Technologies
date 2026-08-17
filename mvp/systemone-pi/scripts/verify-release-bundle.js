const fs=require('fs');
const path=require('path');
const {verifyReleaseManifest}=require('../lib/release-bundle');

const root=path.resolve(__dirname,'..');
const manifestPath=path.join(root,'RELEASE-MANIFEST.json');
if(!fs.existsSync(manifestPath)){console.error('Release-Verifikation blockiert: RELEASE-MANIFEST.json fehlt.');process.exit(2)}
const manifest=JSON.parse(fs.readFileSync(manifestPath,'utf8'));
verifyReleaseManifest(root,manifest);
console.log(`Release-Manifest verifiziert: ${manifest.files.length} Dateien · Commit ${manifest.sourceCommit}`);
