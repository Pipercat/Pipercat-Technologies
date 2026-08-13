const fs=require('fs');
const path=require('path');
const crypto=require('crypto');
const {createRecoveryCode,verifyRecovery}=require('./recovery-code');

const WINDOW_MS=10*60*1000;
function recoveryError(code,message){return Object.assign(new Error(message),{code})}
class RecoveryManager{
  constructor(dataDir,{now=()=>Date.now()}={}){this.dataDir=dataDir;this.now=now;this.recordFile=path.join(dataDir,'recovery-record.json');this.windowFile=path.join(dataDir,'recovery-window.json');fs.mkdirSync(dataDir,{recursive:true,mode:0o700})}
  write(file,value){const temp=`${file}.${process.pid}.tmp`;fs.writeFileSync(temp,`${JSON.stringify(value,null,2)}\n`,{mode:0o600,flag:'wx'});fs.renameSync(temp,file);fs.chmodSync(file,0o600)}
  read(file){try{return JSON.parse(fs.readFileSync(file,'utf8'))}catch(error){if(error.code==='ENOENT')return null;throw recoveryError('RECOVERY_STORAGE_INVALID','Recovery-Zustand ist nicht lesbar.')}}
  provision(){if(this.read(this.recordFile))return null;const created=createRecoveryCode(this.now());this.write(this.recordFile,created.record);return created.code}
  open(){if(!this.read(this.recordFile))throw recoveryError('RECOVERY_CODE_UNAVAILABLE','Recovery-Code wurde noch nicht provisioniert.');const openedAt=new Date(this.now()),window={id:`recovery-${crypto.randomBytes(8).toString('hex')}`,openedAt:openedAt.toISOString(),expiresAt:new Date(openedAt.getTime()+WINDOW_MS).toISOString()};this.write(this.windowFile,window);return{openedAt:window.openedAt,expiresAt:window.expiresAt}}
  status(){const provisioned=Boolean(this.read(this.recordFile)),window=this.read(this.windowFile),now=this.now();if(!window||Date.parse(window.expiresAt)<=now){if(window)try{fs.unlinkSync(this.windowFile)}catch{}return{provisioned,open:false,expiresAt:null}}return{provisioned,open:true,expiresAt:window.expiresAt}}
  recover(code){if(!this.status().open)throw recoveryError('RECOVERY_PHYSICAL_PRESENCE_REQUIRED','Recovery muss zuerst direkt am SystemONE Pi geöffnet werden.');const record=this.read(this.recordFile);try{verifyRecovery(record,{code,physicalPresence:true},this.now())}catch(error){this.write(this.recordFile,record);throw error}try{fs.unlinkSync(this.windowFile)}catch{}const next=createRecoveryCode(this.now());this.write(this.recordFile,next.record);return{recovered:true,recoveryCode:next.code}}
}
module.exports={WINDOW_MS,RecoveryManager};
