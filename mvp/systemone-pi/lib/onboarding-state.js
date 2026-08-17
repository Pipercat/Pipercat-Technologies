const VERSION = 1;
const STEPS = Object.freeze(['welcome', 'language', 'theme', 'home', 'admin', 'integration', 'device', 'review', 'complete']);

function onboardingError(message, details = {}) { return Object.assign(new Error(message), { code: 'ONBOARDING_STATE_INVALID', details }); }
function indexOf(step) { const index = STEPS.indexOf(step); if (index < 0) throw onboardingError('Unbekannter Onboarding-Schritt.', { step }); return index; }

function createOnboardingState(input = {}) {
  const currentStep = STEPS.includes(input.currentStep) ? input.currentStep : 'welcome';
  const completedSteps = Array.isArray(input.completedSteps) ? [...new Set(input.completedSteps.filter(step => STEPS.includes(step) && step !== 'complete'))] : [];
  return {
    version: VERSION,
    currentStep,
    completedSteps,
    startedAt: input.startedAt || new Date().toISOString(),
    updatedAt: input.updatedAt || new Date().toISOString(),
    completedAt: currentStep === 'complete' ? (input.completedAt || new Date().toISOString()) : null
  };
}

function migrateOnboardingState(onboarding = {}) {
  if (onboarding.flow?.version === VERSION) return createOnboardingState(onboarding.flow);
  const legacyComplete = onboarding.completed === true;
  return createOnboardingState({ currentStep: legacyComplete ? 'complete' : 'welcome', completedSteps: legacyComplete ? STEPS.slice(0, -1) : [] });
}

function advanceOnboarding(flow, targetStep) {
  const current = createOnboardingState(flow);
  const currentIndex = indexOf(current.currentStep), targetIndex = indexOf(targetStep);
  if (current.currentStep === 'complete') throw onboardingError('Onboarding ist bereits abgeschlossen.');
  if (targetIndex !== currentIndex + 1) throw onboardingError('Onboarding-Schritte müssen in der vorgesehenen Reihenfolge abgeschlossen werden.', { currentStep: current.currentStep, targetStep });
  const completedSteps = current.completedSteps.includes(current.currentStep) ? current.completedSteps : [...current.completedSteps, current.currentStep];
  return createOnboardingState({ ...current, currentStep: targetStep, completedSteps, completedAt: targetStep === 'complete' ? new Date().toISOString() : null, updatedAt: new Date().toISOString() });
}

function resumeOnboarding(flow) { return createOnboardingState(flow); }

function resetOnboarding() { return createOnboardingState(); }

module.exports = { VERSION, STEPS, createOnboardingState, migrateOnboardingState, advanceOnboarding, resumeOnboarding, resetOnboarding };
