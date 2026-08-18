/**
 * Traveler Finance - Main Application Entry Point
 * Refactored modular version using ES6 modules
 */

import { state, updateState } from "./state.js";
import {
  renderSummary,
  renderLoans,
  renderJournal,
  setupJournalFilter,
  syncSelectElements,
  syncTripControls,
} from "./renderer.js";
import { wireFormHandlers, wireInteractions } from "./forms.js";
import { wireTabNavigation } from "./nav.js";
import { toast } from "./utils.js";
import {
  getAuthStatus,
  login,
  register,
  logout,
  getTrips,
  getTripUsers,
  getTripSummary,
  getLoans,
  getJournal,
} from "./api.js";

let handlersWired = false;
let authMode = "login";

function setAuthView(isAuthenticated, user = null, usersCount = 0) {
  const authView = document.querySelector("#authView");
  const appMain = document.querySelector("#appMain");
  const authTitle = document.querySelector("#authTitle");
  const authSubmit = document.querySelector("#authSubmit");
  const authHint = document.querySelector("#authHint");
  const authModeSwitch = document.querySelector("#authModeSwitch");

  updateState({ user });
  authView?.classList.toggle("hidden", isAuthenticated);
  appMain?.classList.toggle("hidden", !isAuthenticated);
  
  if (isAuthenticated && user) {
    import("./renderer.js").then(({ renderUserInfo }) => {
      renderUserInfo();
    }).catch(() => {});
  }

  const isFirstUser = usersCount === 0;
  if (isFirstUser) {
    authMode = "register";
  }

  authModeSwitch?.classList.toggle("hidden", isFirstUser);
  authModeSwitch?.querySelectorAll("[data-auth-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.authMode === authMode);
  });

  const isRegister = authMode === "register";
  if (authTitle) authTitle.textContent = isRegister ? "Регистрация" : "Вход";
  if (authSubmit) authSubmit.textContent = isRegister ? "Создать аккаунт" : "Войти";
  if (authHint) {
    authHint.textContent = isFirstUser
      ? "Первый пользователь получит существующие путешествия."
      : isRegister
        ? "Создайте отдельный аккаунт для своих путешествий."
        : "Введите имя пользователя и пароль.";
  }
}

function wireAuth(onAuthenticated) {
  const form = document.querySelector("#authForm");
  const authModeSwitch = document.querySelector("#authModeSwitch");
  const logoutBtn = document.querySelector("#logoutBtn");

  authModeSwitch?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-auth-mode]");
    if (!button) return;

    authMode = button.dataset.authMode;
    getAuthStatus()
      .then((status) => setAuthView(false, null, status.users_count))
      .catch((error) => toast(error.message));
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(form).entries());
    const status = await getAuthStatus();
    try {
      const shouldRegister = status.users_count === 0 || authMode === "register";
      const result = shouldRegister ? await register(payload) : await login(payload);
      form.reset();
      setAuthView(true, result.user, status.users_count || 1);
      await onAuthenticated();
      toast(shouldRegister ? "Аккаунт создан" : "Вы вошли");
    } catch (error) {
      toast(error.message);
    }
  });

  logoutBtn?.addEventListener("click", async () => {
    try {
      await logout();
      localStorage.removeItem("travelerFinanceTripId");
      updateState({
        user: null,
        tripId: null,
        trip: null,
        trips: [],
        tripUsers: [],
        families: [],
        summary: null,
        journal: [],
      });
      const status = await getAuthStatus();
      setAuthView(false, null, status.users_count);
      toast("Вы вышли из аккаунта");
    } catch (error) {
      toast(error.message);
    }
  });
}

/**
 * Load all trips and ensure current trip is selected
 */
async function loadTrips() {
  const trips = await getTrips();
  updateState({ trips });

  if (!state.trips.length) {
    localStorage.removeItem("travelerFinanceTripId");
    updateState({ tripId: null, trip: null, summary: null, families: [] });
    syncTripControls();
    document.querySelectorAll(".tab").forEach((button) =>
      button.classList.toggle("active", button.dataset.view === "settings")
    );
    document.querySelectorAll(".view").forEach((view) =>
      view.classList.toggle("active", view.id === "settings")
    );
    return;
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

  const [summary, tripUsers] = await Promise.all([
    getTripSummary(state.tripId),
    getTripUsers(state.tripId),
  ]);
  updateState({ summary, tripUsers });

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
  setupJournalFilter();
}

/**
 * Refresh all data
 */
async function refreshAll() {
  try {
    await loadTrips();
    await loadSummary();

    const activeView = document.querySelector(".view.active")?.id;

    if (activeView === "loans") {
      await loadLoansView();
    }

    if (activeView === "journal") {
      await loadJournalView();
    }
  } catch (error) {
    if (error.status === 401) {
      const status = await getAuthStatus();
      setAuthView(false, null, status.users_count);
      return;
    }
    throw error;
  }
}

function wireAppHandlers() {
  if (handlersWired) return;
  wireTabNavigation(loadLoansView, loadJournalView);
  wireFormHandlers(refreshAll);
  wireInteractions(refreshAll);
  handlersWired = true;
}

/**
 * Initialize application
 */
async function init() {
  try {
    wireAuth(async () => {
      wireAppHandlers();
      await refreshAll();
    });

    const auth = await getAuthStatus();
    setAuthView(auth.authenticated, auth.user, auth.users_count);

    if (!auth.authenticated) {
      return;
    }

    wireAppHandlers();
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
