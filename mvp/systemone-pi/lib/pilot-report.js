'use strict';

const SEVERITIES=new Set(['P0','P1','P2','P3']);
const OUTCOMES=new Set(['completed','aborted','pending']);

function requireText(value,field){
  if(typeof value!=='string'||!value.trim())throw Object.assign(new Error(`${field} fehlt`),{code:'PILOT_REPORT_INVALID'});
  return value.trim();
}

function evaluatePilotReport(input={}){
  const report={
    pilotId:requireText(input.pilotId,'pilotId'),
    participantAlias:requireText(input.participantAlias,'participantAlias'),
    startedAt:requireText(input.startedAt,'startedAt'),
    endedAt:input.endedAt?requireText(input.endedAt,'endedAt'):null,
    outcome:OUTCOMES.has(input.outcome)?input.outcome:'pending',
    onboardingWithoutDeveloper:Boolean(input.onboardingWithoutDeveloper),
    priorHomeAssistantKnowledge:Boolean(input.priorHomeAssistantKnowledge),
    supportMinutes:Number.isFinite(input.supportMinutes)&&input.supportMinutes>=0?input.supportMinutes:0,
    supportContacts:Number.isInteger(input.supportContacts)&&input.supportContacts>=0?input.supportContacts:0,
    issues:Array.isArray(input.issues)?input.issues.map((issue,index)=>({
      id:requireText(issue.id||`issue-${index+1}`,'issue.id'),
      severity:SEVERITIES.has(issue.severity)?issue.severity:'P3',
      code:requireText(issue.code,'issue.code'),
      status:['open','closed'].includes(issue.status)?issue.status:'open',
      action:requireText(issue.action,'issue.action')
    })):[]
  };
  const criticalOpen=report.issues.filter(issue=>issue.status==='open'&&(issue.severity==='P0'||issue.severity==='P1'));
  const gates={
    noSpecialistKnowledge:!report.priorHomeAssistantKnowledge,
    independentOnboarding:report.onboardingWithoutDeveloper,
    supportRecorded:Number.isFinite(report.supportMinutes)&&Number.isInteger(report.supportContacts),
    noOpenCriticalIssues:criticalOpen.length===0,
    participantCompleted:report.outcome==='completed'&&Boolean(report.endedAt)
  };
  return {...report,gates,criticalOpen:criticalOpen.map(issue=>issue.id),releaseReady:Object.values(gates).every(Boolean)};
}

function publicPilotSummary(input){
  const report=evaluatePilotReport(input);
  return {pilotId:report.pilotId,outcome:report.outcome,supportMinutes:report.supportMinutes,supportContacts:report.supportContacts,issueCounts:report.issues.reduce((all,item)=>({...all,[item.severity]:(all[item.severity]||0)+1}),{}),gates:report.gates,criticalOpen:report.criticalOpen,releaseReady:report.releaseReady};
}

module.exports={evaluatePilotReport,publicPilotSummary};
