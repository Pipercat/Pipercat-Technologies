'use strict';

function createGracefulShutdown({stop,persist,close,exit=code=>process.exit(code),timeoutMs=10000,logger=console}={}){
  if(typeof stop!=='function'||typeof persist!=='function'||typeof close!=='function')throw Object.assign(new Error('Shutdown-Abhängigkeiten fehlen.'),{code:'SHUTDOWN_CONFIG_INVALID'});
  let active=null;
  return function shutdown(signal='SIGTERM'){
    if(active)return active;
    active=new Promise(resolve=>{
      let settled=false,timeout;
      const finish=(forced,error=null)=>{
        if(settled)return;
        settled=true;
        if(timeout)clearTimeout(timeout);
        const result={signal,forced,error:error?String(error.message||error):null};
        (error?logger.error:logger.info)?.(`SystemONE beendet${forced?' (Timeout)':''}: ${signal}${result.error?` · ${result.error}`:''}`);
        resolve(result);
        exit(error?1:forced?1:0);
      };
      timeout=setTimeout(()=>finish(true),timeoutMs);timeout.unref?.();
      try{
        stop();
        persist();
        close(error=>finish(false,error||null));
      }catch(error){finish(false,error)}
    });
    return active;
  };
}

module.exports={createGracefulShutdown};
