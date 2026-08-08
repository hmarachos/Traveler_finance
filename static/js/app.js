/**
 * Traveler Finance - Main Application Entry Point
 * Refactored modular version using ES6 modules
 */

import { state, updateState } from "./state.js";
import {
  renderSummary,
  renderLoans,
  renderJournal,
  syncSelectElements,
  syncTripControls,
} from "./renderer.js";
import { wireFormHandlers, wireInteractions } from "./forms.js";
import { wireTabNavigation } from "./nav.js";
import { toast } from "./utils.js";
import {
  getTrips,
  getTripSummary,
  getLoans,
  getJournal,
} from "./api.js";

/**
 * Load all trips and ensure current trip is selected
 */
async function loadTrips() {
  const trips = await getTrips();
  updateState({ trips });

  if (!state.trips.length) {
    throw new Error("Нет доступных путешествий");
  }

  if (!state.tripId || !state.trips.some((trip) => trip.id === state.tripId)) {
    updateState({ tripId: state.trips[0].id });
  }

  syncTripControls();
}

/**
 * Load trip summary and render dashboard
 */
async function loadSummary() {
  if (!state.tripId) return;

  const summary = await getTripSummary(state.tripId);
  updateState({ summary });

  renderSummary();
}

/**
 * Load loans and render list
 */
async function loadLoansView() {
  if (!state.tripId) return;

  const loans = await getLoans(state.tripId);
  renderLoans(loans);
}

/**
 * Load journal and render timeline
 */
async function loadJournalView() {
  if (!state.tripId) return;

  const items = await getJournal(state.tripId);
  renderJournal(items);
}

/**
 * Refresh all data
 */
async function refreshAll() {
  await loadTrips();
  await loadSummary();
}

/**
 * Initialize application
 */
async function init() {
  try {
    // Wire event handlers
    wireTabNavigation(loadLoansView, loadJournalView);
    wireFormHandlers(refreshAll);
    wireInteractions(refreshAll);

    // Load initial data
    await refreshAll();

    // Register service worker for PWA
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    }
  } catch (error) {
    toast(error.message);
  }
}

// Start application
init();
