/**
 * VibeTrip Agent - Travel Planner Form, Loading Coordinator & Itinerary Cache Reuse
 */

const CURRENT_ITINERARY_KEY = 'vibetrip_current_itinerary_v1';
let isPlanningInProgress = false;

/**
 * Safely retrieve the current active itinerary from localStorage
 */
function getCurrentCachedItinerary() {
  try {
    const raw = localStorage.getItem(CURRENT_ITINERARY_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    if (!parsed.plan || !parsed.inputs) return null;
    return parsed;
  } catch (err) {
    console.warn('Failed to parse current itinerary from localStorage:', err);
    return null;
  }
}
window.getCurrentCachedItinerary = getCurrentCachedItinerary;

/**
 * Save the generated itinerary and parameters to localStorage and update hero banner
 */
function saveCurrentItinerary(inputs, plan) {
  try {
    const entry = {
      version: '1.0',
      timestamp: Date.now(),
      inputs: inputs,
      plan: plan,
    };
    localStorage.setItem(CURRENT_ITINERARY_KEY, JSON.stringify(entry));
    updateCachedTripBanner();
  } catch (err) {
    console.warn('Failed to persist current itinerary to localStorage:', err);
  }
}
window.saveCurrentItinerary = saveCurrentItinerary;

/**
 * Compare two sets of planning input parameters for equivalence
 */
function areInputsMatching(a, b) {
  if (!a || !b) return false;
  const norm = (s) => (s ?? '').toString().trim().toLowerCase();
  
  if (norm(a.destination) !== norm(b.destination)) return false;
  if (parseInt(a.duration_days, 10) !== parseInt(b.duration_days, 10)) return false;
  if (norm(a.travel_pace || 'balanced') !== norm(b.travel_pace || 'balanced')) return false;
  if (parseInt(a.travelers || 1, 10) !== parseInt(b.travelers || 1, 10)) return false;
  
  const bA = a.budget === null || a.budget === undefined || isNaN(a.budget) ? null : Number(a.budget);
  const bB = b.budget === null || b.budget === undefined || isNaN(b.budget) ? null : Number(b.budget);
  if (bA !== bB) return false;

  if (norm(a.currency || 'USD') !== norm(b.currency || 'USD')) return false;
  if (norm(a.start_date || '') !== norm(b.start_date || '')) return false;
  if (norm(a.end_date || '') !== norm(b.end_date || '')) return false;

  const sortArr = (arr) => (Array.isArray(arr) ? [...arr].map(s => norm(s)).sort().join(',') : '');
  if (sortArr(a.interests) !== sortArr(b.interests)) return false;
  if (sortArr(a.atmosphere) !== sortArr(b.atmosphere)) return false;

  return true;
}

/**
 * Update the Hero "View Current Itinerary" Banner based on active cache
 */
function updateCachedTripBanner() {
  const banner = document.getElementById('cachedTripBanner');
  const label = document.getElementById('cachedTripLabel');
  const btn = document.getElementById('btnViewCachedTrip');
  if (!banner || !label || !btn) return;

  const cached = getCurrentCachedItinerary();
  if (cached && cached.plan && cached.plan.destination) {
    const days = cached.plan.itinerary?.length || cached.inputs.duration_days || 3;
    label.textContent = `Active itinerary available for ${cached.plan.destination} (${days} Days)`;
    banner.style.display = 'inline-flex';

    btn.onclick = (e) => {
      e.preventDefault();
      const resultsSection = document.getElementById('resultsSection');
      if (resultsSection) {
        window.results.renderPlan(cached.plan);
        resultsSection.classList.add('active');
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        window.showToast(`Displaying your active ${cached.plan.destination} itinerary.`, 'info');
      }
    };
  } else {
    banner.style.display = 'none';
  }
}
window.updateCachedTripBanner = updateCachedTripBanner;

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('plannerForm');
  if (!form) return;

  // Initialize cached trip banner on load
  updateCachedTripBanner();

  // Validate active cached itinerary against backend health
  (async () => {
    try {
      if (window.api && typeof window.api.getHealth === 'function') {
        const health = await window.api.getHealth();
        if (health && health.integrations) {
          const cached = getCurrentCachedItinerary();
          if (cached && cached.plan && Array.isArray(cached.plan.warnings)) {
            const hasStaleUnconfiguredWarning = cached.plan.warnings.some(w => {
              const lower = w.toLowerCase();
              return (
                (lower.includes('qloo api is not configured') && health.integrations.qloo === 'configured') ||
                (lower.includes('geoapify api is not configured') && health.integrations.geoapify === 'configured') ||
                (lower.includes('groq api is not configured') && health.integrations.groq === 'configured')
              );
            });
            if (hasStaleUnconfiguredWarning) {
              console.info('Clearing stale degraded itinerary cache; integrations are now active.');
              localStorage.removeItem(CURRENT_ITINERARY_KEY);
              updateCachedTripBanner();
            }
          }
        }
      }
    } catch (err) {
      console.debug('Health check skipped on load:', err);
    }
  })();

  // Selected state arrays
  let selectedInterests = ['cafes', 'architecture', 'photography'];
  let selectedAtmosphere = ['artistic', 'peaceful'];
  let selectedPace = 'balanced';

  // Chip Selector Handlers
  document.querySelectorAll('.interest-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const val = chip.dataset.val;
      if (selectedInterests.includes(val)) {
        selectedInterests = selectedInterests.filter(i => i !== val);
        chip.classList.remove('active');
      } else {
        selectedInterests.push(val);
        chip.classList.add('active');
      }
    });
  });

  document.querySelectorAll('.atmosphere-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const val = chip.dataset.val;
      if (selectedAtmosphere.includes(val)) {
        selectedAtmosphere = selectedAtmosphere.filter(a => a !== val);
        chip.classList.remove('active');
      } else {
        selectedAtmosphere.push(val);
        chip.classList.add('active');
      }
    });
  });

  // Pace Card Handlers
  document.querySelectorAll('.pace-card').forEach(card => {
    card.addEventListener('click', () => {
      document.querySelectorAll('.pace-card').forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      selectedPace = card.dataset.pace;
    });
  });

  // Quick Destination Chips
  document.querySelectorAll('.quick-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const destInput = document.getElementById('destinationInput');
      if (destInput) {
        destInput.value = chip.dataset.dest;
        destInput.focus();
      }
    });
  });

  // Date vs Duration Sync
  const startDateInput = document.getElementById('startDateInput');
  const endDateInput = document.getElementById('endDateInput');
  const durationInput = document.getElementById('durationInput');

  function updateDurationFromDates() {
    if (startDateInput && endDateInput && startDateInput.value && endDateInput.value) {
      const start = new Date(startDateInput.value);
      const end = new Date(endDateInput.value);
      if (end >= start) {
        const diffTime = Math.abs(end - start);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
        if (durationInput) durationInput.value = diffDays;
      }
    }
  }

  if (startDateInput && endDateInput) {
    startDateInput.addEventListener('change', updateDurationFromDates);
    endDateInput.addEventListener('change', updateDurationFromDates);
  }

  // Form Submission
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Prevent double submits while a request is in flight
    if (isPlanningInProgress) {
      return;
    }

    // Reset error messages
    const destError = document.getElementById('destinationError');
    const destInput = document.getElementById('destinationInput');
    destError.classList.remove('visible');

    const destination = destInput.value.trim();
    if (!destination || destination.length < 2) {
      destError.textContent = 'Please enter a valid destination city (at least 2 characters).';
      destError.classList.add('visible');
      destInput.focus();
      return;
    }

    const durationDays = parseInt(durationInput.value, 10) || 3;
    const travelers = parseInt(document.getElementById('travelersInput').value, 10) || 1;
    const budgetVal = parseFloat(document.getElementById('budgetInput').value);
    const budget = isNaN(budgetVal) ? null : budgetVal;
    const currency = document.getElementById('currencyInput').value || 'USD';
    const startDate = startDateInput.value || null;
    const endDate = endDateInput.value || null;

    const payload = {
      destination,
      duration_days: durationDays,
      start_date: startDate,
      end_date: endDate,
      travelers,
      budget,
      currency,
      interests: [...selectedInterests],
      atmosphere: [...selectedAtmosphere],
      travel_pace: selectedPace,
    };

    // Smart Itinerary Re-use Check
    const cached = getCurrentCachedItinerary();
    const hasUnconfiguredWarnings = cached?.plan?.warnings?.some(w => w.toLowerCase().includes('not configured'));
    const isDegradedCache = hasUnconfiguredWarnings || Object.values(cached?.plan?.integration_status || {}).some(s => s === 'not_configured');

    if (cached && cached.plan && areInputsMatching(payload, cached.inputs) && !isDegradedCache) {
      // Re-use current generated plan without calling backend or Groq API
      const resultsSection = document.getElementById('resultsSection');
      window.results.renderPlan(cached.plan);
      resultsSection.classList.add('active');
      resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      window.showToast(
        `Showing your current itinerary for ${cached.plan.destination}. Change destination or preferences to generate a new trip.`,
        'info',
        5000
      );
      return;
    }

    await executePlanningFlow(payload);
  });
});

/**
 * Orchestrate the Multi-stage Loading UI and API Call
 */
async function executePlanningFlow(payload) {
  if (isPlanningInProgress) return;
  isPlanningInProgress = true;

  const loadingOverlay = document.getElementById('loadingOverlay');
  const resultsSection = document.getElementById('resultsSection');
  const progressFill = document.getElementById('loadingProgressFill');
  const generateBtn = document.getElementById('generatePlanBtn');

  // Disable button to prevent duplicate clicks
  if (generateBtn) {
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<span>⏳</span> <span>Crafting Your VibeTrip...</span>';
  }

  // Stages DOM
  const step1 = document.getElementById('step1');
  const step2 = document.getElementById('step2');
  const step3 = document.getElementById('step3');
  const step4 = document.getElementById('step4');
  const step5 = document.getElementById('step5');

  // Reset steps
  [step1, step2, step3, step4, step5].forEach(s => {
    if (s) {
      s.className = 'loading-step';
      const icon = s.querySelector('.step-status-icon');
      if (icon) icon.textContent = '○';
    }
  });

  // Show loading
  if (loadingOverlay) {
    loadingOverlay.classList.add('active');
    loadingOverlay.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  if (resultsSection) {
    resultsSection.classList.remove('active');
  }

  // Stage 1: Understanding vibe
  if (step1) {
    step1.classList.add('active');
    const icon = step1.querySelector('.step-status-icon');
    if (icon) icon.textContent = '⋯';
  }
  if (progressFill) progressFill.style.width = '20%';

  try {
    // Initiate actual API call
    const apiPromise = window.api.planTrip(payload);

    // Progressive stage transitions reflecting real steps
    setTimeout(() => {
      if (step1) {
        step1.className = 'loading-step completed';
        const icon = step1.querySelector('.step-status-icon');
        if (icon) icon.textContent = '✓';
      }
      if (step2) {
        step2.classList.add('active');
        const icon = step2.querySelector('.step-status-icon');
        if (icon) icon.textContent = '⋯';
      }
      if (progressFill) progressFill.style.width = '40%';
    }, 600);

    setTimeout(() => {
      if (step2) {
        step2.className = 'loading-step completed';
        const icon = step2.querySelector('.step-status-icon');
        if (icon) icon.textContent = '✓';
      }
      if (step3) {
        step3.classList.add('active');
        const icon = step3.querySelector('.step-status-icon');
        if (icon) icon.textContent = '⋯';
      }
      if (progressFill) progressFill.style.width = '65%';
    }, 1200);

    setTimeout(() => {
      if (step3) {
        step3.className = 'loading-step completed';
        const icon = step3.querySelector('.step-status-icon');
        if (icon) icon.textContent = '✓';
      }
      if (step4) {
        step4.classList.add('active');
        const icon = step4.querySelector('.step-status-icon');
        if (icon) icon.textContent = '⋯';
      }
      if (progressFill) progressFill.style.width = '85%';
    }, 1800);

    const planData = await apiPromise;

    // Cache the newly generated plan and input parameters
    saveCurrentItinerary(payload, planData);

    // Stage 5: Finalizing
    if (step4) {
      step4.className = 'loading-step completed';
      const icon = step4.querySelector('.step-status-icon');
      if (icon) icon.textContent = '✓';
    }
    if (step5) {
      step5.classList.add('active');
      const icon = step5.querySelector('.step-status-icon');
      if (icon) icon.textContent = '⋯';
    }
    if (progressFill) progressFill.style.width = '100%';

    // Update statuses according to actual data returned
    if (planData.integration_status?.qloo !== 'success' && step2) {
      step2.className = 'loading-step skipped';
      const icon = step2.querySelector('.step-status-icon');
      if (icon) icon.textContent = '—';
      const label = step2.querySelector('span:last-child');
      const qlooStatus = planData.integration_status?.qloo;
      if (label) {
        label.textContent = qlooStatus === 'not_configured'
          ? 'Qloo insights (unconfigured / skipped)'
          : 'Qloo insights (temporarily unavailable / skipped)';
      }
    }

    if (planData.integration_status?.geoapify !== 'success' && step3) {
      step3.className = 'loading-step skipped';
      const icon = step3.querySelector('.step-status-icon');
      if (icon) icon.textContent = '—';
      const label = step3.querySelector('span:last-child');
      const geoStatus = planData.integration_status?.geoapify;
      if (label) {
        label.textContent = geoStatus === 'not_configured'
          ? 'Geoapify places (unconfigured / skipped)'
          : 'Geoapify places (temporarily unavailable / skipped)';
      }
    }

    const aiSuccess = planData.integration_status?.groq === 'success' || planData.integration_status?.gemini === 'success';
    if (!aiSuccess && step4) {
      step4.className = 'loading-step skipped';
      const icon = step4.querySelector('.step-status-icon');
      if (icon) icon.textContent = '—';
      const label = step4.querySelector('span:last-child');
      const groqStatus = planData.integration_status?.groq;
      if (label) {
        label.textContent = groqStatus === 'not_configured'
          ? 'AI reasoning (unconfigured / rule fallback)'
          : 'AI reasoning (temporarily unavailable / rule fallback)';
      }
    }


    setTimeout(() => {
      if (step5) {
        step5.className = 'loading-step completed';
        const icon = step5.querySelector('.step-status-icon');
        if (icon) icon.textContent = '✓';
      }

      setTimeout(() => {
        if (loadingOverlay) loadingOverlay.classList.remove('active');
        window.results.renderPlan(planData);
        if (resultsSection) {
          resultsSection.classList.add('active');
          resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        window.showToast('Your personalized itinerary is ready!', 'success');
      }, 400);
    }, 400);

  } catch (err) {
    if (loadingOverlay) loadingOverlay.classList.remove('active');
    console.error('Plan generation failed:', err);
    window.showToast(err.message || 'Failed to generate itinerary. Please try again.', 'error', 6000);
  } finally {
    isPlanningInProgress = false;
    if (generateBtn) {
      generateBtn.disabled = false;
      generateBtn.innerHTML = '<span>⚡</span> <span>Generate My VibeTrip Itinerary</span>';
    }
  }
}
