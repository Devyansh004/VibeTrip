/**
 * VibeTrip Agent - Results Dashboard Renderer
 * Handles itinerary rendering, place selection (include/exclude),
 * and post-generation natural language personalization with Groq GPT-OSS-20B.
 */

class ResultsRenderer {
  constructor() {
    this.currentPlan = null;
    this.currentTripKey = null;
    this.savedPlaces = new Set();
    this.selectedPlaceIds = new Set();
    this.excludedPlaceIds = new Set();
    this.isPersonalizing = false;
    this.eventsBound = false;
  }

  /**
   * Render the complete travel plan into #resultsContainer
   */
  renderPlan(plan) {
    if (!plan) return;
    const container = document.getElementById('resultsContainer');
    if (!container) return;

    // Synchronize place selection state with the current trip.
    // Reset selections only if we are rendering a distinctly different trip.
    const tripKey = plan.trip_id || `${plan.destination}_${plan.preferences?.start_date || ''}_${plan.itinerary?.length || 0}`;
    if (this.currentTripKey !== tripKey) {
      this.currentTripKey = tripKey;
      this.selectedPlaceIds = new Set();
      this.excludedPlaceIds = new Set();
    }

    // Prune any selection IDs that do not exist in recommended_places
    const authoritativeIds = new Set((plan.recommended_places || []).map(p => p.place_id));
    for (const pid of Array.from(this.selectedPlaceIds)) {
      if (!authoritativeIds.has(pid)) this.selectedPlaceIds.delete(pid);
    }
    for (const pid of Array.from(this.excludedPlaceIds)) {
      if (!authoritativeIds.has(pid)) this.excludedPlaceIds.delete(pid);
    }

    this.currentPlan = plan;

    const {
      destination,
      summary,
      preferences,
      recommended_places,
      itinerary,
      estimated_budget,
      integration_status,
      warnings,
    } = plan;

    const durationDays = itinerary ? itinerary.length : (preferences?.duration_days || 1);
    const travelers = preferences?.travelers || 1;
    const budgetStr = estimated_budget 
      ? `${estimated_budget.currency || 'USD'} ${estimated_budget.estimated_total}` 
      : 'Flexible';

    const html = `
      <!-- Trip Overview Card -->
      <div class="trip-overview-card" id="tripOverviewCard">
        <div class="trip-overview-top">
          <div class="trip-title-area">
            <span class="editorial-tag">Custom Curated Itinerary</span>
            <h2 id="overviewDestinationTitle">${window.escapeHtml(destination)}</h2>
            <div class="trip-meta-badges">
              <span class="meta-badge" id="badgeDuration">
                <svg class="meta-badge-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/></svg>
                <span>${durationDays} Days</span>
              </span>
              <span class="meta-badge" id="badgeTravelers">
                <svg class="meta-badge-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                <span>${travelers} Traveler${travelers > 1 ? 's' : ''}</span>
              </span>
              <span class="meta-badge" id="badgeBudget">
                <svg class="meta-badge-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/></svg>
                <span>${budgetStr}</span>
              </span>
              <span class="meta-badge" id="badgePace">
                <svg class="meta-badge-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/></svg>
                <span>Pace: ${window.escapeHtml(preferences?.travel_pace || 'Balanced')}</span>
              </span>
            </div>
          </div>
          <div class="trip-actions">
            <button id="saveTripBtn" class="btn btn-primary btn-sm">
              <span>💾</span> Save Trip
            </button>
            <button id="regenerateBtn" class="btn btn-secondary btn-sm">
              <span>↻</span> Plan Another
            </button>
            <button onclick="window.print()" class="btn btn-outline btn-sm">
              <span>⎙</span> Print
            </button>
          </div>
        </div>

        <!-- Integration Status Banner -->
        <div id="integrationStatusContainer">
          ${this.renderIntegrationStatusBanner(integration_status)}
        </div>

        <!-- Warnings Banner -->
        <div id="overviewWarningsContainer">
          ${this.renderWarningsHtml(warnings)}
        </div>

        <!-- Editorial Atmosphere Summary -->
        <div class="editorial-summary-card">
          <span class="editorial-tag">Vibe & Style Synthesis</span>
          <p class="editorial-text" id="editorialSummaryText">${window.escapeHtml(summary)}</p>
        </div>
      </div>

      <!-- Recommended Real Places Section -->
      <div id="placesSectionContainer" style="margin-bottom: 48px;">
        <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 12px; margin-bottom: 6px;">
          <h3 class="section-headline">Curated Places Matching Your Vibe</h3>
          <span style="font-size: 0.85rem; color: var(--color-text-muted);">
            Use <strong>Include</strong> or <strong>Exclude</strong> to guide itinerary personalization
          </span>
        </div>
        <p class="section-subheadline">
          Grounded venue discoveries discovered via geospatial search and cultural affinity scoring.
        </p>

        ${recommended_places && recommended_places.length > 0 ? `
          <div class="places-grid" id="placesGrid">
            ${recommended_places.map(place => this.renderPlaceCard(place)).join('')}
          </div>
        ` : `
          <div class="card" style="text-align: center; color: var(--color-text-muted); padding: 40px;">
            <p>No verified venues found matching these exact filters. Suggesting neighborhood discovery instead.</p>
          </div>
        `}
      </div>

      <!-- Dedicated Post-Generation Personalization Section -->
      <div class="personalization-section" id="personalizationSection">
        <div class="personalization-card" id="personalizationCard">
          <div class="personalization-header">
            <div class="personalization-title-group">
              <span class="editorial-tag">Interactive Refinement</span>
              <h3 class="personalization-title">Personalize your itinerary</h3>
              <p class="personalization-subtitle">
                Guide Groq to adjust pacing, prioritize your selected places, remove unwanted stops, or restructure daily activities to match your travel mood.
              </p>
            </div>
            <div class="personalization-badge">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
              <span>Powered by Groq GPT-OSS-20B</span>
            </div>
          </div>

          <!-- Selection Summary Bar -->
          <div class="personalization-selection-bar" id="personalizationSelectionBar">
            ${this.renderSelectionSummaryHtml()}
          </div>

          <!-- Natural Language Textarea -->
          <div class="form-group" style="margin-bottom: 12px;">
            <label for="personalizeInput" class="form-label">
              <span>Personalization instructions</span>
              <span class="form-label-hint">3 to 1,500 characters</span>
            </label>
            <textarea 
              id="personalizeInput" 
              class="form-input personalize-textarea" 
              rows="3" 
              maxlength="1500" 
              placeholder="e.g., Reduce walking, keep Day 2 relaxed, and prioritize my selected cafes."
            ></textarea>
            <div class="personalize-meta-row">
              <span class="char-count" id="personalizeCharCount">0 / 1500 characters</span>
              <div class="quick-prompts">
                <span class="quick-prompt-label">Suggestions:</span>
                <button type="button" class="quick-prompt-chip" data-prompt="Reduce walking, keep Day 2 relaxed, and prioritize my selected cafes.">
                  Relax Day 2 & Cafes
                </button>
                <button type="button" class="quick-prompt-chip" data-prompt="Schedule museum and indoor cultural visits during the afternoon heat.">
                  Afternoon Culture
                </button>
                <button type="button" class="quick-prompt-chip" data-prompt="Cluster activities geographically to minimize transit time between stops.">
                  Cluster Geographically
                </button>
              </div>
            </div>
          </div>

          <!-- Validation / Error / Success Feedback Container -->
          <div id="personalizeFeedback" class="personalize-feedback" style="display: none;"></div>

          <!-- Action Buttons -->
          <div class="personalization-actions">
            <button type="button" id="updateItineraryBtn" class="btn btn-primary">
              <span class="btn-icon-symbol">⚡</span>
              <span class="btn-label-text">Update itinerary</span>
            </button>
            <button type="button" id="clearPersonalizeBtn" class="btn btn-outline btn-sm">
              Clear
            </button>
          </div>
        </div>
      </div>

      <!-- Day-by-Day Itinerary Timeline -->
      <div class="itinerary-container" id="itineraryContainer">
        <h3 class="section-headline">Day-by-Day Journey</h3>
        <p class="section-subheadline" id="itineraryPaceSubheadline">
          Chronological schedule designed for a ${window.escapeHtml(preferences?.travel_pace || 'balanced')} rhythm.
        </p>

        <div id="timelineDaysList">
          ${itinerary && itinerary.length > 0 ? itinerary.map(day => this.renderDayTimeline(day)).join('') : ''}
        </div>
      </div>

      <!-- Estimated Budget Breakdown Card -->
      <div id="budgetCardContainer">
        ${estimated_budget ? this.renderBudgetCard(estimated_budget) : ''}
      </div>
    `;

    container.innerHTML = html;

    // Attach delegated event listeners once
    this.bindEvents();
  }

  /**
   * Render single place card with Include and Exclude controls
   */
  renderPlaceCard(place) {
    const isIncluded = this.selectedPlaceIds.has(place.place_id);
    const isExcluded = this.excludedPlaceIds.has(place.place_id);
    const isSaved = this.savedPlaces.has(place.place_id);

    let cardClass = '';
    let statusBadgeHtml = '';

    if (isIncluded) {
      cardClass = 'is-selected-include';
      statusBadgeHtml = '<span class="place-state-badge badge-included">✓ Included</span>';
    } else if (isExcluded) {
      cardClass = 'is-selected-exclude';
      statusBadgeHtml = '<span class="place-state-badge badge-excluded">✕ Excluded</span>';
    }

    return `
      <div class="place-card ${cardClass}" data-place-id="${place.place_id}">
        <div class="place-header">
          <div class="place-category-group">
            <span class="place-category">${window.escapeHtml(place.category || 'Spot')}</span>
            ${statusBadgeHtml}
          </div>
          <span class="place-provenance">${window.escapeHtml(place.data_source)}</span>
        </div>
        <h4 class="place-name">${window.escapeHtml(place.name)}</h4>
        <p class="place-address">
          <span>📍</span> ${window.escapeHtml(place.address || 'Local neighborhood')}
        </p>
        ${place.match_explanation ? `
          <div class="place-match">
            ${window.escapeHtml(place.match_explanation)}
          </div>
        ` : ''}
        <div class="place-footer">
          <span class="place-time">⏱ ~${place.estimated_visit_minutes || 60} mins</span>
          <div class="place-actions">
            ${place.map_url ? `
              <a href="${place.map_url}" target="_blank" rel="noopener noreferrer" class="place-link">
                Directions ↗
              </a>
            ` : ''}
            <button class="btn btn-outline btn-sm save-place-btn" data-id="${place.place_id}" data-name="${window.escapeHtml(place.name)}">
              ${isSaved ? '★ Saved' : '☆ Save'}
            </button>
          </div>
        </div>

        <!-- Place Selection Controls for Personalization -->
        <div class="place-selection-bar">
          <button 
            type="button" 
            class="place-select-btn btn-include ${isIncluded ? 'active' : ''}" 
            data-action="include" 
            data-id="${place.place_id}" 
            data-name="${window.escapeHtml(place.name)}"
            title="${isIncluded ? 'Click to deselect' : 'Prioritize this place in your personalized itinerary'}"
          >
            ${isIncluded ? '✓ Included' : '+ Include'}
          </button>
          <button 
            type="button" 
            class="place-select-btn btn-exclude ${isExcluded ? 'active' : ''}" 
            data-action="exclude" 
            data-id="${place.place_id}" 
            data-name="${window.escapeHtml(place.name)}"
            title="${isExcluded ? 'Click to deselect' : 'Exclude this place from your itinerary'}"
          >
            ${isExcluded ? '✕ Excluded' : '✕ Exclude'}
          </button>
        </div>
      </div>
    `;
  }

  /**
   * Render HTML for the selection summary bar
   */
  renderSelectionSummaryHtml() {
    const includedCount = this.selectedPlaceIds.size;
    const excludedCount = this.excludedPlaceIds.size;

    if (includedCount === 0 && excludedCount === 0) {
      return `
        <div class="selection-summary-text">
          <span class="selection-empty-hint">
            <svg class="selection-pin-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/></svg>
            No places specifically selected or excluded yet. Click <strong>+ Include</strong> or <strong>✕ Exclude</strong> on any place card above.
          </span>
        </div>
      `;
    }

    const placesMap = new Map((this.currentPlan?.recommended_places || []).map(p => [p.place_id, p.name]));

    const includedPills = Array.from(this.selectedPlaceIds).map(id => {
      const name = placesMap.get(id) || id;
      return `<span class="selection-pill included">✓ ${window.escapeHtml(name)}</span>`;
    }).join(' ');

    const excludedPills = Array.from(this.excludedPlaceIds).map(id => {
      const name = placesMap.get(id) || id;
      return `<span class="selection-pill excluded">✕ ${window.escapeHtml(name)}</span>`;
    }).join(' ');

    return `
      <div class="selection-summary-text">
        <strong>Active Selections:</strong>
        ${includedCount > 0 ? `<span>${includedCount} to include: ${includedPills}</span>` : ''}
        ${excludedCount > 0 ? `<span>${excludedCount} excluded: ${excludedPills}</span>` : ''}
      </div>
      <button type="button" class="btn btn-outline btn-sm" id="resetPlaceSelectionsBtn" style="font-size: 0.75rem; padding: 4px 10px;">
        Reset Selections
      </button>
    `;
  }

  /**
   * Render integration status banner HTML
   */
  renderIntegrationStatusBanner(integration_status) {
    if (!integration_status) return '';
    const qloo = integration_status.qloo || 'not_configured';
    const geo = integration_status.geoapify || 'not_configured';
    const groq = integration_status.groq || 'not_configured';

    const getPillClass = (st) => (st === 'success' ? 'success' : st === 'not_configured' ? 'not_configured' : 'failed');
    const getPillLabel = (st) => {
      if (st === 'success') return '✓ Active';
      if (st === 'not_configured') return '○ Unconfigured';
      return '⚠ Fallback';
    };

    return `
      <div class="integration-status-banner" id="integrationStatusBanner" style="margin-top: 14px; margin-bottom: 14px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <strong style="color: var(--color-text);">Service Integrations:</strong>
          <span style="color: var(--color-text-muted); font-size: 0.8rem;">Live execution provenance</span>
        </div>
        <div class="integration-pills">
          <span class="integration-pill ${getPillClass(qloo)}">
            Qloo Taste: ${getPillLabel(qloo)}
          </span>
          <span class="integration-pill ${getPillClass(geo)}">
            Geoapify Places: ${getPillLabel(geo)}
          </span>
          <span class="integration-pill ${getPillClass(groq)}">
            Groq AI: ${getPillLabel(groq)}
          </span>
        </div>
      </div>
    `;
  }

  /**
   * Render warnings list HTML
   */
  renderWarningsHtml(warnings) {
    if (!warnings || warnings.length === 0) return '';
    return `
      <div class="warnings-banner">
        <strong>Advisory Notes & Degradation Transparency:</strong>
        <ul>
          ${warnings.map(w => `<li>${window.escapeHtml(w)}</li>`).join('')}
        </ul>
      </div>
    `;
  }

  /**
   * Render single day card in itinerary
   */
  renderDayTimeline(day) {
    return `
      <div class="day-card">
        <div class="day-header">
          <div class="day-title-group">
            <span class="day-badge">Day ${day.day_number}</span>
            <h4 class="day-theme">${window.escapeHtml(day.theme)}</h4>
          </div>
          ${day.date ? `<span class="day-date">${new Date(day.date).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</span>` : ''}
        </div>

        ${day.notes ? `
          <div class="day-notes">
            <strong>Insider Note:</strong> ${window.escapeHtml(day.notes)}
          </div>
        ` : ''}

        <div class="timeline">
          ${day.activities.map(act => this.renderActivityItem(act)).join('')}
        </div>
      </div>
    `;
  }

  /**
   * Render single activity in timeline
   */
  renderActivityItem(act) {
    return `
      <div class="timeline-item">
        <div class="timeline-dot"></div>
        <div class="activity-card">
          <div class="activity-header">
            <span class="time-bracket-badge">${window.escapeHtml(act.time_label || 'Activity')}</span>
            <div class="activity-meta">
              ${act.estimated_duration_minutes ? `<span>⏱ ${act.estimated_duration_minutes}m</span>` : ''}
              ${act.estimated_cost ? `<span>~${act.currency || 'USD'} ${act.estimated_cost}</span>` : ''}
              ${act.is_estimate ? `<span style="font-size: 0.72rem; color: #9CA2AF;">(est.)</span>` : ''}
            </div>
          </div>
          <h5 class="activity-title">${window.escapeHtml(act.title)}</h5>
          <p class="activity-desc">${window.escapeHtml(act.description)}</p>
          ${this.renderActivityVenueLink(act)}
        </div>
      </div>
    `;
  }

  /**
   * Render verified venue map link for an activity using real location information.
   * Never displays raw internal IDs. Omits link if real location data is unavailable.
   */
  renderActivityVenueLink(act) {
    if (!act.place_id) return '';

    const destination = this.currentPlan?.destination || '';
    const matchedPlace = this.currentPlan?.recommended_places?.find(p => p.place_id === act.place_id);

    let mapUrl = null;
    let venueName = '';

    if (matchedPlace) {
      venueName = matchedPlace.name || '';

      if (matchedPlace.map_url) {
        mapUrl = matchedPlace.map_url;
      } else if (matchedPlace.latitude != null && matchedPlace.longitude != null) {
        mapUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(matchedPlace.latitude + ',' + matchedPlace.longitude)}`;
      } else if (matchedPlace.address) {
        mapUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(matchedPlace.address)}`;
      } else if (matchedPlace.name) {
        const query = destination ? `${matchedPlace.name}, ${destination}` : matchedPlace.name;
        mapUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
      }
    }

    if (mapUrl) {
      const labelText = venueName 
        ? `View ${window.escapeHtml(venueName)} on Map`
        : 'View on Map';

      return `
        <div style="margin-top: 10px;">
          <a 
            href="${mapUrl}" 
            target="_blank" 
            rel="noopener noreferrer" 
            class="activity-venue-link" 
            data-place-id="${window.escapeHtml(act.place_id)}"
            title="Open ${venueName ? window.escapeHtml(venueName) : 'location'} in Google Maps"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/></svg>
            <span>${labelText}</span>
            <span aria-hidden="true" style="font-size: 0.72rem; opacity: 0.85;">↗</span>
          </a>
        </div>
      `;
    }

    return '';
  }

  /**
   * Render estimated budget card
   */
  renderBudgetCard(budget) {
    const cats = budget.categories || {};
    return `
      <div class="budget-card">
        <div class="budget-header">
          <div>
            <h3 class="section-headline" style="margin-bottom: 2px;">Estimated Budget Plan</h3>
            <p style="color: var(--color-text-muted); font-size: 0.85rem;">Advisory estimate for budgeting expectations</p>
          </div>
          <div style="text-align: right;">
            <span style="font-size: 0.8rem; color: var(--color-text-muted);">Estimated Total</span>
            <div style="font-size: 1.8rem; font-weight: 700; color: var(--color-accent);">
              ${budget.currency || 'USD'} ${budget.estimated_total}
            </div>
          </div>
        </div>

        <div class="budget-categories">
          <div class="budget-cat-item">
            <div class="budget-cat-label">Activities & Admissions</div>
            <div class="budget-cat-value">${budget.currency || 'USD'} ${cats.activities || 0}</div>
          </div>
          <div class="budget-cat-item">
            <div class="budget-cat-label">Dining & Cafes</div>
            <div class="budget-cat-value">${budget.currency || 'USD'} ${cats.food_and_drink || 0}</div>
          </div>
          <div class="budget-cat-item">
            <div class="budget-cat-label">Local Transit</div>
            <div class="budget-cat-value">${budget.currency || 'USD'} ${cats.transit || 0}</div>
          </div>
        </div>

        <p class="budget-disclaimer">
          * ${window.escapeHtml(budget.note || 'All cost estimates are planning benchmarks and subject to seasonal variability.')}
        </p>
      </div>
    `;
  }

  /**
   * Bind event listeners with delegation to prevent leaks or duplicate listeners
   */
  bindEvents() {
    if (this.eventsBound) return;
    this.eventsBound = true;

    const container = document.getElementById('resultsContainer');
    if (!container) return;

    // Delegated click handler
    container.addEventListener('click', (e) => {
      // 1. Place selection Include/Exclude buttons
      const selectBtn = e.target.closest('.place-select-btn');
      if (selectBtn) {
        if (this.isPersonalizing) return;
        const placeId = selectBtn.dataset.id;
        const action = selectBtn.dataset.action;
        this.handlePlaceAction(placeId, action);
        return;
      }

      // 2. Save place bookmark
      const savePlaceBtn = e.target.closest('.save-place-btn');
      if (savePlaceBtn) {
        const placeId = savePlaceBtn.dataset.id;
        const placeName = savePlaceBtn.dataset.name;
        this.toggleSavePlace(placeId, placeName, savePlaceBtn);
        return;
      }

      // 3. Reset all place selections
      const resetBtn = e.target.closest('#resetPlaceSelectionsBtn');
      if (resetBtn) {
        this.selectedPlaceIds.clear();
        this.excludedPlaceIds.clear();
        this.updatePlaceCardsUI();
        this.updateSelectionSummaryUI();
        window.showToast('Place selections reset.');
        return;
      }

      // 4. Quick prompt suggestions
      const promptChip = e.target.closest('.quick-prompt-chip');
      if (promptChip) {
        const input = document.getElementById('personalizeInput');
        if (input && !this.isPersonalizing) {
          input.value = promptChip.dataset.prompt;
          this.updateCharCount();
          input.focus();
        }
        return;
      }

      // 5. Clear personalization input
      const clearBtn = e.target.closest('#clearPersonalizeBtn');
      if (clearBtn) {
        if (this.isPersonalizing) return;
        const input = document.getElementById('personalizeInput');
        if (input) {
          input.value = '';
          this.updateCharCount();
          input.focus();
        }
        this.hidePersonalizeFeedback();
        return;
      }

      // 6. Update Itinerary submit button
      const updateBtn = e.target.closest('#updateItineraryBtn');
      if (updateBtn) {
        this.handlePersonalize();
        return;
      }

      // 7. Save trip button
      const saveTripBtn = e.target.closest('#saveTripBtn');
      if (saveTripBtn) {
        this.handleSaveTrip();
        return;
      }

      // 8. Plan another button
      const regenBtn = e.target.closest('#regenerateBtn');
      if (regenBtn) {
        const plannerSection = document.getElementById('plannerSection');
        if (plannerSection) {
          plannerSection.scrollIntoView({ behavior: 'smooth' });
          window.showToast('Adjust preferences and generate a new trip.', 'info');
        }
        return;
      }
    });

    // Delegated input handler for textarea character counting and error clearing
    container.addEventListener('input', (e) => {
      if (e.target.id === 'personalizeInput') {
        this.updateCharCount();
        this.hidePersonalizeFeedback();
      }
    });
  }

  /**
   * Handle place Include or Exclude action with strict mutual exclusivity
   */
  handlePlaceAction(placeId, action) {
    if (!placeId) return;

    if (action === 'include') {
      if (this.selectedPlaceIds.has(placeId)) {
        this.selectedPlaceIds.delete(placeId);
      } else {
        this.selectedPlaceIds.add(placeId);
        this.excludedPlaceIds.delete(placeId); // Enforce mutual exclusivity
      }
    } else if (action === 'exclude') {
      if (this.excludedPlaceIds.has(placeId)) {
        this.excludedPlaceIds.delete(placeId);
      } else {
        this.excludedPlaceIds.add(placeId);
        this.selectedPlaceIds.delete(placeId); // Enforce mutual exclusivity
      }
    }

    this.updatePlaceCardsUI();
    this.updateSelectionSummaryUI();
  }

  /**
   * Update place card styles, badges, and button labels without full page re-render
   */
  updatePlaceCardsUI() {
    const cards = document.querySelectorAll('.place-card[data-place-id]');
    cards.forEach(card => {
      const placeId = card.dataset.placeId;
      const isIncluded = this.selectedPlaceIds.has(placeId);
      const isExcluded = this.excludedPlaceIds.has(placeId);

      // Card active classes
      card.classList.toggle('is-selected-include', isIncluded);
      card.classList.toggle('is-selected-exclude', isExcluded);

      // Status badge in header
      const categoryGroup = card.querySelector('.place-category-group');
      if (categoryGroup) {
        const existingBadge = categoryGroup.querySelector('.place-state-badge');
        if (existingBadge) existingBadge.remove();

        if (isIncluded) {
          const badge = document.createElement('span');
          badge.className = 'place-state-badge badge-included';
          badge.textContent = '✓ Included';
          categoryGroup.appendChild(badge);
        } else if (isExcluded) {
          const badge = document.createElement('span');
          badge.className = 'place-state-badge badge-excluded';
          badge.textContent = '✕ Excluded';
          categoryGroup.appendChild(badge);
        }
      }

      // Buttons
      const incBtn = card.querySelector('.btn-include');
      if (incBtn) {
        incBtn.classList.toggle('active', isIncluded);
        incBtn.textContent = isIncluded ? '✓ Included' : '+ Include';
      }

      const excBtn = card.querySelector('.btn-exclude');
      if (excBtn) {
        excBtn.classList.toggle('active', isExcluded);
        excBtn.textContent = isExcluded ? '✕ Excluded' : '✕ Exclude';
      }
    });
  }

  /**
   * Update the selection summary bar
   */
  updateSelectionSummaryUI() {
    const bar = document.getElementById('personalizationSelectionBar');
    if (bar) {
      bar.innerHTML = this.renderSelectionSummaryHtml();
    }
  }

  /**
   * Update character counter in the personalization form
   */
  updateCharCount() {
    const input = document.getElementById('personalizeInput');
    const counter = document.getElementById('personalizeCharCount');
    if (input && counter) {
      const len = input.value.length;
      counter.textContent = `${len} / 1500 characters`;
      if (len > 1500) {
        counter.style.color = 'var(--color-error)';
      } else {
        counter.style.color = 'var(--color-text-muted)';
      }
    }
  }

  /**
   * Show feedback in the personalization feedback box
   */
  showPersonalizeFeedback(message, type = 'error') {
    const box = document.getElementById('personalizeFeedback');
    if (!box) return;

    box.className = `personalize-feedback feedback-${type}`;
    box.style.display = 'block';

    const icon = type === 'success' ? '✓' : type === 'warning' ? '⚠' : '⚠️';
    box.innerHTML = `<strong>${icon}</strong> <span>${window.escapeHtml(message)}</span>`;
  }

  /**
   * Hide the personalization feedback box
   */
  hidePersonalizeFeedback() {
    const box = document.getElementById('personalizeFeedback');
    if (box) {
      box.style.display = 'none';
      box.innerHTML = '';
    }
  }

  /**
   * Execute post-generation itinerary personalization via POST /api/plan/personalize
   */
  async handlePersonalize() {
    if (this.isPersonalizing || !this.currentPlan) return;

    const input = document.getElementById('personalizeInput');
    const instructions = (input?.value || '').trim();

    // Client-side validation matching backend PersonalizePlanRequest
    if (instructions.length < 3) {
      this.showPersonalizeFeedback(
        'Please enter personalization instructions (at least 3 characters). For example: "Reduce walking, keep Day 2 relaxed, and prioritize my selected cafes."',
        'error'
      );
      input?.focus();
      return;
    }

    if (instructions.length > 1500) {
      this.showPersonalizeFeedback(
        'Instructions cannot exceed 1,500 characters. Please shorten your request.',
        'error'
      );
      input?.focus();
      return;
    }

    // Set Loading State
    this.isPersonalizing = true;
    const updateBtn = document.getElementById('updateItineraryBtn');
    const clearBtn = document.getElementById('clearPersonalizeBtn');
    if (updateBtn) {
      updateBtn.disabled = true;
      updateBtn.innerHTML = '<span class="inline-spinner"></span> <span>Updating itinerary with Groq...</span>';
    }
    if (clearBtn) clearBtn.disabled = true;
    if (input) input.disabled = true;

    // Disable all selection buttons during request
    document.querySelectorAll('.place-select-btn').forEach(b => b.disabled = true);
    this.hidePersonalizeFeedback();

    try {
      // Build request payload conforming exactly to PersonalizePlanRequest schema
      const selectedPlaceIds = Array.from(this.selectedPlaceIds);
      const excludedPlaceIds = Array.from(this.excludedPlaceIds);
      const isSavedTrip = this.currentPlan.trip_id && !this.currentPlan.trip_id.startsWith('guest_');

      const payload = {
        instructions: instructions,
        selected_place_ids: selectedPlaceIds,
        excluded_place_ids: excludedPlaceIds,
        current_plan: this.currentPlan,
        trip_id: isSavedTrip ? this.currentPlan.trip_id : null,
      };

      const updatedPlan = await window.api.personalizeTrip(payload);

      // Update current plan in state
      this.currentPlan = updatedPlan;

      // Update local storage if trip was saved in guest mode
      const localTrips = this.getGuestTrips();
      const savedIndex = localTrips.findIndex(t => t.id === updatedPlan.trip_id);
      if (savedIndex !== -1) {
        localTrips[savedIndex].plan = updatedPlan;
        localTrips[savedIndex].summary = updatedPlan.summary;
        localTrips[savedIndex].budget = updatedPlan.estimated_budget?.estimated_total;
        localTrips[savedIndex].updated_at = new Date().toISOString();
        this.saveGuestTrips(localTrips);
      }

      // Update session cached itinerary if active
      if (typeof window.saveCurrentItinerary === 'function' && typeof window.getCurrentCachedItinerary === 'function') {
        const cached = window.getCurrentCachedItinerary();
        if (cached && cached.inputs) {
          window.saveCurrentItinerary(cached.inputs, updatedPlan);
        }
      }

      // Re-render updated timeline
      const timelineDaysList = document.getElementById('timelineDaysList');
      if (timelineDaysList && updatedPlan.itinerary) {
        timelineDaysList.innerHTML = updatedPlan.itinerary.map(day => this.renderDayTimeline(day)).join('');
      }

      // Update editorial summary text
      const summaryEl = document.getElementById('editorialSummaryText');
      if (summaryEl && updatedPlan.summary) {
        summaryEl.textContent = updatedPlan.summary;
      }

      // Update budget card
      const budgetContainer = document.getElementById('budgetCardContainer');
      if (budgetContainer) {
        budgetContainer.innerHTML = updatedPlan.estimated_budget ? this.renderBudgetCard(updatedPlan.estimated_budget) : '';
      }

      // Update integration status banner honestly
      const bannerContainer = document.getElementById('integrationStatusContainer');
      if (bannerContainer) {
        bannerContainer.innerHTML = this.renderIntegrationStatusBanner(updatedPlan.integration_status);
      }

      // Update warnings banner honestly
      const warningsContainer = document.getElementById('overviewWarningsContainer');
      if (warningsContainer) {
        warningsContainer.innerHTML = this.renderWarningsHtml(updatedPlan.warnings);
      }

      // Refresh selection summary UI
      this.updateSelectionSummaryUI();

      // Show success feedback
      this.showPersonalizeFeedback(
        'Itinerary successfully personalized! Your schedule has been updated with Groq GPT-OSS-20B reasoning.',
        'success'
      );
      window.showToast('Itinerary successfully updated!', 'success');

      // Scroll smoothly to timeline
      const itineraryContainer = document.getElementById('itineraryContainer');
      if (itineraryContainer) {
        itineraryContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }

    } catch (err) {
      console.error('Itinerary personalization failed:', err);
      // PRESERVE PREVIOUS ITINERARY INTACT
      const errorMsg = err?.data?.detail || err?.message || 'Failed to personalize itinerary. Please check your instructions and try again.';
      this.showPersonalizeFeedback(errorMsg, 'error');
      window.showToast('Personalization failed. Original itinerary preserved.', 'error');
    } finally {
      // Reset loading state
      this.isPersonalizing = false;
      if (updateBtn) {
        updateBtn.disabled = false;
        updateBtn.innerHTML = '<span class="btn-icon-symbol">⚡</span> <span class="btn-label-text">Update itinerary</span>';
      }
      if (clearBtn) clearBtn.disabled = false;
      if (input) {
        input.disabled = false;
        input.focus();
      }
      document.querySelectorAll('.place-select-btn').forEach(b => b.disabled = false);
    }
  }

  /**
   * Bookmark or unbookmark a place
   */
  toggleSavePlace(placeId, placeName, buttonEl) {
    if (this.savedPlaces.has(placeId)) {
      this.savedPlaces.delete(placeId);
      buttonEl.textContent = '☆ Save';
      window.showToast(`Removed ${placeName} from saved places.`);
    } else {
      this.savedPlaces.add(placeId);
      buttonEl.textContent = '★ Saved';
      window.showToast(`Saved ${placeName} to your places!`, 'success');
    }
  }

  /**
   * Safely retrieve guest trips from localStorage, handling malformed data gracefully.
   */
  getGuestTrips() {
    try {
      const raw = localStorage.getItem('vibetrip_guest_trips');
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed.filter(item => item && typeof item === 'object' && item.id);
    } catch (e) {
      console.warn('Failed to parse guest trips from localStorage, recovering:', e);
      return [];
    }
  }

  /**
   * Safely persist guest trips to localStorage, strictly enforcing the 20-trip maximum limit.
   */
  saveGuestTrips(trips) {
    try {
      const validTrips = Array.isArray(trips) ? trips.slice(0, 20) : [];
      localStorage.setItem('vibetrip_guest_trips', JSON.stringify(validTrips));
    } catch (e) {
      console.warn('Failed to save guest trips to localStorage:', e);
    }
  }

  /**
   * Save trip to saved journeys in localStorage
   */
  async handleSaveTrip() {
    if (!this.currentPlan) return;

    try {
      const localTrips = this.getGuestTrips();
      const tripId = this.currentPlan.trip_id || `trip_${Date.now()}`;
      if (!this.currentPlan.trip_id) {
        this.currentPlan.trip_id = tripId;
      }

      const existingIdx = localTrips.findIndex(t => t.id === tripId);
      const existingTrip = existingIdx !== -1 ? localTrips[existingIdx] : null;

      const newTrip = {
        id: tripId,
        user_id: 'guest',
        title: `${this.currentPlan.destination} Vibe Trip`,
        destination: this.currentPlan.destination,
        duration_days: this.currentPlan.itinerary ? this.currentPlan.itinerary.length : 1,
        budget: this.currentPlan.estimated_budget?.estimated_total,
        currency: this.currentPlan.estimated_budget?.currency || 'USD',
        plan: this.currentPlan,
        created_at: existingTrip?.created_at || new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      
      // Update if already exists or prepend, keeping no duplicate entries
      if (existingIdx !== -1) {
        localTrips.splice(existingIdx, 1);
      }
      localTrips.unshift(newTrip);

      // Enforce the 20 most recent unique trips cap
      this.saveGuestTrips(localTrips);
      
      window.showToast('Trip successfully saved to your saved journeys!', 'success');
    } catch (err) {
      console.error('Failed to save trip:', err);
      window.showToast('Failed to save trip to your collection.', 'error');
    }
  }
}

window.results = new ResultsRenderer();
