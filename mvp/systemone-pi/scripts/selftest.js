const assert=require('assert');const fs=require('fs');const os=require('os');const path=require('path');const {LocalStorage}=require('../lib/storage');const {HueAdapter}=require('../lib/hue');const {Diagnostics}=require('../lib/diagnostics');
const demo=[{id:'hue-1',hueId:'1',integration:'hue',type:'light',name:'Testlicht',online:true,on:false,brightness:50}];
async function adapter(fault=''){process.env.HUE_MODE='simulation';process.env.HUE_SIM_FAULT=fault;const dir=fs.mkdtempSync(path.join(os.tmpdir(),'systemone-test-'));const storage=new LocalStorage(dir);return {hue:new HueAdapter({storage,demoDevices:demo,diagnostics:new Diagnostics()}),dir}}
(async()=>{let passed=0;async function test(name,fn){try{await fn();passed++;console.log(`✓ ${name}`)}catch(e){console.error(`✗ ${name}: ${e.message}`);process.exitCode=1}}
await test('Simulation spricht keine echte Bridge an',async()=>{const {hue}=await adapter();assert.equal(hue.mode,'simulation');const b=await hue.discover();assert.equal(b.ip,'127.0.0.1')});
await test('Bridge nicht gefunden',async()=>{const {hue}=await adapter('not-found');assert.equal(await hue.discover(),null)});
await test('Link-Button-Fehler',async()=>{const {hue}=await adapter('link-button');await hue.discover();await assert.rejects(()=>hue.pair(),e=>e.code==='HUE_LINK_BUTTON_REQUIRED')});
await test('Timeout-Fehler',async()=>{const {hue}=await adapter('timeout');await hue.discover();await hue.pair();await assert.rejects(()=>hue.fetchLights(),e=>e.code==='HUE_TIMEOUT')});
await test('Auth-Fehler',async()=>{const {hue}=await adapter('auth');await hue.discover();await hue.pair();await assert.rejects(()=>hue.fetchLights(),e=>e.code==='HUE_AUTH_ERROR')});
await test('Offline-Gerät',async()=>{const {hue}=await adapter('offline');await hue.discover();await hue.pair();const lights=await hue.fetchLights();assert.equal(lights[0].online,false)});
await test('Befehlsfehler',async()=>{const {hue}=await adapter('command');await hue.discover();await hue.pair();await assert.rejects(()=>hue.setLight(demo[0],{on:true}),e=>e.code==='HUE_COMMAND_FAILED')});
await test('Persistenz schreibt und liest Zustand',async()=>{const {dir}=await adapter();const s=new LocalStorage(dir);s.saveState({ok:true});assert.equal(s.loadState({}).ok,true)});
console.log(`\n${passed}/8 Tests bestanden`);if(passed!==8)process.exitCode=1})().catch(e=>{console.error(e);process.exit(1)});
