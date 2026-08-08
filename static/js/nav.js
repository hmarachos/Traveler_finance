/**
 * Navigation and tab handling module
 */

import { qs, qsa } from "./utils.js";

/**
 * Wire tab navigation
 */
export function wireTabNavigation(onLoansLoad, onJournalLoad) {
  qsa(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      // Update active tab
      qsa(".tab").forEach((b) => b.classList.toggle("active", b === button));

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
