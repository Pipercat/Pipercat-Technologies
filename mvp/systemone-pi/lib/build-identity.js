const fs=require('fs');
const path=require('path');
const {verifyReleaseManifest}=require('./release-bundle');

function loadBuildIdentity(root,{readFileSync=fs.readFileSync,existsSync=fs.existsSync,verify=verifyReleaseManifest}={}){const pkg=JSON.parse(readFileSync(path.join(root,'package.json'),'utf8')),manifestPath=path.join(root,'RELEASE-MANIFEST.json');if(!existsSync(manifestPath))return{version:pkg.version,target:'systemone-pi',channel:'development',verified:false,sourceCommit:null,sourceTimestamp:null};let manifest;try{manifest=JSON.parse(readFileSync(manifestPath,'utf8'));verify(root,manifest)}catch(cause){throw Object.assign(new Error('Installierte Release-Identität konnte nicht verifiziert werden.'),{code:'BUILD_IDENTITY_INVALID',cause})}if(manifest.version!==pkg.version||manifest.name!==pkg.name)throw Object.assign(new Error('Release-Manifest und Paketversion stimmen nicht überein.'),{code:'BUILD_IDENTITY_MISMATCH'});return{version:manifest.version,target:manifest.target,channel:'release',verified:true,sourceCommit:manifest.sourceCommit,sourceTimestamp:manifest.sourceTimestamp}}
function publicBuildIdentity(identity){return{version:identity.version,target:identity.target,channel:identity.channel,verified:Boolean(identity.verified),sourceCommit:identity.sourceCommit,sourceTimestamp:identity.sourceTimestamp}}

module.exports={loadBuildIdentity,publicBuildIdentity};
