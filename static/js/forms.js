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
  updateFamily,
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

    // Edit family button handler
    const editFamilyButton = event.target.closest("[data-edit-family]");
    if (editFamilyButton) {
      const familyId = editFamilyButton.dataset.editFamily;
      const familyRow = editFamilyButton.closest(".family-row");
      const viewDiv = familyRow.querySelector("div:first-child");
      const editForm = familyRow.querySelector(`[data-family-edit="${familyId}"]`);
      
      // Hide the view, show the edit form
      viewDiv.querySelector("strong").style.display = "none";
      viewDiv.querySelector(".meta").style.display = "none";
      editForm.classList.remove("hidden");
      editFamilyButton.style.display = "none";
      familyRow.querySelector(`[data-delete-family="${familyId}"]`).style.display = "none";
      
      // Add event listener to the edit form if not already added
      const submitBtn = editForm.querySelector('button[type="submit"]');
      if (submitBtn && !submitBtn.dataset.hasListener) {
        submitBtn.dataset.hasListener = "true";
        editForm.addEventListener("submit", async (e) => {
          e.preventDefault();
          const formData = formPayload(editForm);
          try {
            await updateFamily(state.tripId, familyId, formData);
            await onDataChange();
            toast("Семья обновлена");
          } catch (error) {
            toast(error.message);
          }
        });
      }
      return;
    }

    // Cancel edit handler
    const cancelEditButton = event.target.closest("[data-cancel-edit]");
    if (cancelEditButton) {
      const familyId = cancelEditButton.dataset.cancelEdit;
      const familyRow = cancelEditButton.closest(".family-row");
      const viewDiv = familyRow.querySelector("div:first-child");
      const editForm = familyRow.querySelector(`[data-family-edit="${familyId}"]`);
      
      // Show the view, hide the edit form
      viewDiv.querySelector("strong").style.display = "block";
      viewDiv.querySelector(".meta").style.display = "block";
      editForm.classList.add("hidden");
      familyRow.querySelector(`[data-edit-family="${familyId}"]`).style.display = "inline-block";
      familyRow.querySelector(`[data-delete-family="${familyId}"]`).style.display = "inline-block";
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
