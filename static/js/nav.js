/**
 * Navigation and tab handling module
 */

import { qs, qsa } from "./utils.js";

/**
 * Wire tab navigation (desktop and mobile)
 */
export function wireTabNavigation(onLoansLoad, onJournalLoad) {
  // Desktop tabs
  qsa(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      // Update active tab
      qsa(".tab").forEach((b) => b.classList.toggle("active", b === button));

      // Update mobile nav
      qsa(".mobile-nav-item").forEach((b) =>
        b.classList.toggle("active", b.dataset.view === button.dataset.view)
      );

      // Update active view
      qsa(".view").forEach((view) =>
        view.classList.toggle("active", view.id === button.dataset.view)
      );

      // Load view-specific data
      if (button.dataset.view === "loans") {
        onLoansLoad();
      }

      if (button.dataset.view === "journal") {
        onJournalLoad();
      }
    });
  });

  // Mobile navigation
  qsa(".mobile-nav-item").forEach((button) => {
    button.addEventListener("click", () => {
      // Update active mobile nav
      qsa(".mobile-nav-item").forEach((b) =>
        b.classList.toggle("active", b === button)
      );

      // Update desktop tabs
      qsa(".tab").forEach((b) =>
        b.classList.toggle("active", b.dataset.view === button.dataset.view)
      );

      // Update active view
      qsa(".view").forEach((view) =>
        view.classList.toggle("active", view.id === button.dataset.view)
      );

      // Load view-specific data
      if (button.dataset.view === "loans") {
        onLoansLoad();
      }

      if (button.dataset.view === "journal") {
        onJournalLoad();
      }
    });
  });

  // Wire form type switcher
  qsa(".segmented button").forEach((button) => {
    button.addEventListener("click", () => {
      qsa(".segmented button").forEach((b) =>
        b.classList.toggle("active", b === button)
      );

      qsa(".entry-form").forEach((form) =>
        form.classList.toggle("active", form.id === button.dataset.form)
      );
    });
  });
}
