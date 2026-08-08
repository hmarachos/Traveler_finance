/**
 * Form handling module
 */

import { state, updateState } from "./state.js";
import {
  qs,
  qsa,
  toast,
  formPayload,
} from "./utils.js";
import {
  createTrip,
  updateTrip,
  deleteTrip,
  createFamily,
  deleteFamily,
  createExpense,
  createTransfer,
  createLoan,
  addLoanRepayment,
} from "./api.js";

/**
 * Wire all form submission handlers
 */
export function wireFormHandlers(onDataChange) {
  // Trip edit form
  qs("#tripEditForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await updateTrip(state.tripId, formPayload(event.currentTarget));
      await onDataChange();
      toast("Путешествие сохранено");
    } catch (error) {
      toast(error.message);
    }
  });

  // Trip create form
  qs("#tripCreateForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      const created = await createTrip(formPayload(form));
      updateState({ tripId: created.id });
      form.reset();
      form.elements.currency.value = "EUR";
      await onDataChange();
      toast("Путешествие создано");
    } catch (error) {
      toast(error.message);
    }
  });

  // Family form
  qs("#familyForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await createFamily(state.tripId, formPayload(form));
      form.reset();
      form.elements.members_count.value = 1;
      await onDataChange();
      toast("Семья добавлена");
    } catch (error) {
      toast(error.message);
    }
  });

  // Expense form
  qs("#expenseForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await createExpense(state.tripId, formPayload(form));
      form.reset();
      await onDataChange();
      toast("Расход добавлен");
    } catch (error) {
      toast(error.message);
    }
  });

  // Transfer form
  qs("#transferForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await createTransfer(state.tripId, formPayload(form));
      form.reset();
      await onDataChange();
      toast("Перевод сохранен");
    } catch (error) {
      toast(error.message);
    }
  });

  // Loan form
  qs("#loanForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await createLoan(state.tripId, formPayload(form));
      form.reset();
      await onDataChange();
      toast("Заем создан");
    } catch (error) {
      toast(error.message);
    }
  });

  // Repayment form
  qs("#repayForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = formPayload(form);
    try {
      await addLoanRepayment(state.tripId, payload.loan_id, payload);
      qs("#repayDialog").close();
      form.reset();
      await onDataChange();
      toast("Возврат сохранен");
    } catch (error) {
      toast(error.message);
    }
  });
}

/**
 * Wire form interactions and delete buttons
 */
export function wireInteractions(onDataChange) {
  // Repay button handler
  document.body.addEventListener("click", (event) => {
    const repayButton = event.target.closest("[data-repay]");
    if (repayButton) {
      qs("#repayForm [name='loan_id']").value = repayButton.dataset.repay;
      qs("#repayDialog").showModal();
      return;
    }

    // Delete family handler
    const deleteFamilyButton = event.target.closest("[data-delete-family]");
    if (deleteFamilyButton) {
      const family = state.families.find(
        (item) =>
          String(item.id) === String(deleteFamilyButton.dataset.deleteFamily)
      );

      if (!family || !confirm(`Удалить семью "${family.name}"?`)) return;

      deleteFamily(state.tripId, family.id)
        .then(onDataChange)
        .then(() => toast("Семья удалена"))
        .catch((error) => toast(error.message));
      return;
    }

    // Switch trip handler
    const switchTripButton = event.target.closest("[data-switch-trip]");
    if (switchTripButton) {
      const tripId = Number(switchTripButton.dataset.switchTrip);
      updateState({ tripId });
      onDataChange();
      return;
    }
  });

  // Trip select handler
  qs("#tripSelect").addEventListener("change", async (event) => {
    updateState({ tripId: Number(event.currentTarget.value) });
    await onDataChange();
    toast("Путешествие открыто");
  });

  // Delete trip handler
  qs("#deleteTripBtn").addEventListener("click", async () => {
    if (
      !state.trip ||
      !confirm(
        `Удалить путешествие "${state.trip.name}"?`
      )
    )
      return;

    try {
      await deleteTrip(state.tripId);
      localStorage.removeItem("travelerFinanceTripId");
      updateState({ tripId: null });
      await onDataChange();
      toast("Путешествие удалено");
    } catch (error) {
      if (error.message.includes("last trip")) {
        toast("Создайте новое путешествие перед тем, как удалить это");
      } else {
        toast(error.message);
      }
    }
  });

  // Refresh button handler
  qs("#refreshBtn").addEventListener("click", () =>
    onDataChange().then(() => toast("Обновлено"))
  );
}
