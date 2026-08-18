/**
 * Navigation and tab handling module
 */

import { qs, qsa } from "./utils.js";

/**
 * Update active state of topbar quick add buttons
 */
function updateQuickAddState(activeFormId = null) {
  const addViewIsActive = qs("#add")?.classList.contains("active");
  qsa("[data-quick-add]").forEach((btn) => {
    if (!addViewIsActive) {
      btn.classList.remove("active");
    } else {
      btn.classList.toggle("active", btn.dataset.quickAdd === activeFormId);
    }
  });
}

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

      // Update topbar quick add button active state
      if (button.dataset.view === "add") {
        const activeFormId = qs(".entry-form.active")?.id || "expenseForm";
        updateQuickAddState(activeFormId);
      } else {
        updateQuickAddState(null);
      }

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

      // Update topbar quick add button active state
      if (button.dataset.view === "add") {
        const activeFormId = qs(".entry-form.active")?.id || "expenseForm";
        updateQuickAddState(activeFormId);
      } else {
        updateQuickAddState(null);
      }

      // Load view-specific data
      if (button.dataset.view === "loans") {
        onLoansLoad();
      }

      if (button.dataset.view === "journal") {
        onJournalLoad();
      }
    });
  });

  // Wire form type switcher (if present)
  qsa(".segmented button").forEach((button) => {
    button.addEventListener("click", () => {
      qsa(".segmented button").forEach((b) =>
        b.classList.toggle("active", b === button)
      );

      qsa(".entry-form").forEach((form) =>
        form.classList.toggle("active", form.id === button.dataset.form)
      );

      updateQuickAddState(button.dataset.form);
    });
  });

  // Wire quick action buttons (e.g. + Расход, + Перевод, + Долг)
  qsa("[data-quick-add]").forEach((button) => {
    button.addEventListener("click", () => {
      const targetForm = button.dataset.quickAdd;

      // Activate 'add' view
      qsa(".tab").forEach((b) => b.classList.toggle("active", b.dataset.view === "add"));
      qsa(".mobile-nav-item").forEach((b) =>
        b.classList.toggle("active", b.dataset.view === "add")
      );
      qsa(".view").forEach((v) => v.classList.toggle("active", v.id === "add"));

      // Activate target form within 'add' view
      if (targetForm) {
        qsa(".entry-form").forEach((form) =>
          form.classList.toggle("active", form.id === targetForm)
        );
      }

      // Highlight active quick add button
      updateQuickAddState(targetForm);
    });
  });

  // Initial state check
  updateQuickAddState(null);
}
