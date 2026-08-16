/**
 * Form handling module
 */

import { state, updateState } from "./state.js";
import {
  qs,
  qsa,
  toast,
  formPayload,
  keepFamilySelectsDifferent,
} from "./utils.js";
import { syncSelectElements } from "./renderer.js";
import {
  createTrip,
  updateTrip,
  deleteTrip,
  addTripUser,
  removeTripUser,
  createFamily,
  updateFamily,
  deleteFamily,
  createExpense,
  createTransfer,
  createLoan,
  addLoanRepayment,
  updateExpense,
  updateTransfer,
  updateLoan,
  deleteExpense,
  deleteTransfer,
  deleteLoan,
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

  qs("#tripUserForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await addTripUser(state.tripId, formPayload(form));
      form.reset();
      await onDataChange();
      toast("Пользователь добавлен");
    } catch (error) {
      toast(error.message);
    }
  });

  // Expense form
  qs("#expenseForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    
    // Validate split method selection
    const splitMethodRadios = form.querySelectorAll('input[name="split_method"]:checked');
    if (splitMethodRadios.length === 0) {
      toast('Пожалуйста, выберите способ распределения');
      return;
    }
    
    // Handle custom category selection
    const categorySelect = document.getElementById('categorySelect');
    const customCategoryInput = document.getElementById('customCategoryInput');
    if (categorySelect && customCategoryInput) {
      if (categorySelect.value === 'Другое' && customCategoryInput.value.trim()) {
        // Use custom category value
        categorySelect.value = customCategoryInput.value.trim();
      } else if (categorySelect.value === 'Другое' && !customCategoryInput.value.trim()) {
        // Show error if custom category is empty
        toast('Пожалуйста, введите название категории');
        return;
      }
    }
    
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
    if (!keepFamilySelectsDifferent(form, "from_family_id", "to_family_id", "from_family_id")) {
      toast("Добавьте минимум две семьи для перевода");
      return;
    }
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
    if (!keepFamilySelectsDifferent(form, "lender_family_id", "borrower_family_id", "lender_family_id")) {
      toast("Добавьте минимум две семьи для займа");
      return;
    }
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
  
  // Edit expense form
  qs("#editExpenseForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const expenseId = form.elements.expense_id.value;
    try {
      await updateExpense(state.tripId, expenseId, formPayload(form));
      qs("#editExpenseDialog").close();
      form.reset();
      await onDataChange();
      toast("Расход обновлен");
    } catch (error) {
      toast(error.message);
    }
  });
  
  // Edit transfer form
  qs("#editTransferForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const transferId = form.elements.transfer_id.value;
    if (!keepFamilySelectsDifferent(form, "from_family_id", "to_family_id", "from_family_id")) {
      toast("Для перевода нужны две разные семьи");
      return;
    }
    try {
      await updateTransfer(state.tripId, transferId, formPayload(form));
      qs("#editTransferDialog").close();
      form.reset();
      await onDataChange();
      toast("Перевод обновлен");
    } catch (error) {
      toast(error.message);
    }
  });
  
  // Edit loan form
  qs("#editLoanForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const loanId = form.elements.loan_id.value;
    if (!keepFamilySelectsDifferent(form, "lender_family_id", "borrower_family_id", "lender_family_id")) {
      toast("Для займа нужны две разные семьи");
      return;
    }
    try {
      await updateLoan(state.tripId, loanId, formPayload(form));
      qs("#editLoanDialog").close();
      form.reset();
      await onDataChange();
      toast("Заем обновлен");
    } catch (error) {
      toast(error.message);
    }
  });
}

/**
 * Wire form interactions and delete buttons
 */
export function wireInteractions(onDataChange) {
  document.body.addEventListener("change", (event) => {
    const select = event.target.closest("select[name$='_family_id']");
    if (!select) return;

    syncFamilySelectPair(select, "#transferForm", "from_family_id", "to_family_id");
    syncFamilySelectPair(select, "#loanForm", "lender_family_id", "borrower_family_id");
    syncFamilySelectPair(select, "#editTransferForm", "from_family_id", "to_family_id");
    syncFamilySelectPair(select, "#editLoanForm", "lender_family_id", "borrower_family_id");
  });

  // Setup edit category handling
  function setupEditCategoryHandling() {
    const categorySelect = document.getElementById('editCategorySelect');
    const customCategoryLabel = document.getElementById('editCustomCategoryLabel');
    const customCategoryInput = document.getElementById('editCustomCategoryInput');
    
    if (!categorySelect || !customCategoryLabel || !customCategoryInput) return;
    
    function updateCategoryVisibility() {
      if (categorySelect.value === 'Другое') {
        customCategoryLabel.classList.remove('hidden');
        customCategoryInput.required = true;
      } else {
        customCategoryLabel.classList.add('hidden');
        customCategoryInput.required = false;
        customCategoryInput.value = '';
      }
    }
    
    updateCategoryVisibility();
    categorySelect.addEventListener('change', updateCategoryVisibility);
  }
  
  setupEditCategoryHandling();
  
  // Repay button handler
  document.body.addEventListener("click", (event) => {
    const repayButton = event.target.closest("[data-repay]");
    if (repayButton) {
      qs("#repayForm [name='loan_id']").value = repayButton.dataset.repay;
      qs("#repayDialog").showModal();
      return;
    }

    const editLoanButton = event.target.closest("[data-edit-loan]");
    if (editLoanButton) {
      openLoanEditor(editLoanButton.dataset.editLoan);
      return;
    }

    const deleteLoanButton = event.target.closest("[data-delete-loan]");
    if (deleteLoanButton) {
      const loanId = deleteLoanButton.dataset.deleteLoan;
      if (!confirm("Удалить этот заем?")) return;
      
      deleteLoan(state.tripId, loanId)
        .then(onDataChange)
        .then(() => toast("Заем удален"))
        .catch((error) => toast(error.message));
      return;
    }
    
    // Click on journal entry (whole container is clickable)
    const timelineItem = event.target.closest(".timeline-item[data-entry-id]");
    if (timelineItem) {
      const entryId = timelineItem.dataset.entryId;
      const entryType = timelineItem.dataset.entryType;
      
      // Helper function to find family ID by name
      function findFamilyIdByName(familyName) {
        const family = state.families.find(f => f.name === familyName.trim());
        return family ? family.id : null;
      }
      
      // Helper function to extract family name from expense meta
      function extractPaidByFamilyName(meta) {
        const parts = meta.split(' · ');
        if (parts.length >= 1 && parts[0].startsWith('Оплатили: ')) {
          return parts[0].replace('Оплатили: ', '').trim();
        }
        return null;
      }
      
      // Helper function to extract family names from transfer/loan meta
      function extractFamilyNamesFromArrow(meta) {
        const parts = meta.split(' → ');
        if (parts.length === 2) {
          return {
            from: parts[0].trim(),
            to: parts[1].trim()
          };
        }
        // Try to extract from "должны" format for loans
        const должныParts = meta.split(' должны ');
        if (должныParts.length === 2) {
          return {
            from: должныParts[0].trim(), // borrower
            to: должныParts[1].trim()    // lender
          };
        }
        return { from: null, to: null };
      }
      
      // Map entry types to form field names
      const typeConfig = {
        'expense': {
          dialogId: '#editExpenseDialog',
          formId: '#editExpenseForm',
          idField: 'expense_id',
          getFormData: (entry) => {
            const metaParts = entry.meta.split(' · ');
            const category = metaParts.length >= 2 ? metaParts[1].trim() : 'Общее';
            const splitMethod = metaParts.length >= 3 ? metaParts[2].trim() : 'equal';
            const paidByFamilyName = extractPaidByFamilyName(entry.meta);
            const paidByFamilyId = paidByFamilyName ? findFamilyIdByName(paidByFamilyName) : null;
            
            // Check if category is in standard categories
            const standardCategories = [
              'Общее', 'Жильё', 'Транспорт', 'Еда', 'Продукты', 
              'Развлечения', 'Сувениры', 'Здоровье', 'Связь', 
              'Страховка', 'Парковка', 'Туалеты', 'Другое'
            ];
            const categoryValue = standardCategories.includes(category) ? category : 'Другое';
            const customCategory = standardCategories.includes(category) ? '' : category;
            
            return {
              description: entry.title,
              amount: (entry.amount_minor / 100).toFixed(2),
              category: categoryValue,
              custom_category: customCategory,
              paid_by_family_id: paidByFamilyId || (state.families.length > 0 ? state.families[0].id : '1'),
              split_method: splitMethod
            };
          }
        },
        'transfer': {
          dialogId: '#editTransferDialog',
          formId: '#editTransferForm',
          idField: 'transfer_id',
          getFormData: (entry) => {
            const familyNames = extractFamilyNamesFromArrow(entry.meta);
            const fromFamilyId = familyNames.from ? findFamilyIdByName(familyNames.from) : null;
            const toFamilyId = familyNames.to ? findFamilyIdByName(familyNames.to) : null;
            
            return {
              from_family_id: fromFamilyId || (state.families.length > 0 ? state.families[0].id : '1'),
              to_family_id: toFamilyId || (state.families.length > 0 ? state.families[0].id : '1'),
              amount: (entry.amount_minor / 100).toFixed(2),
              transfer_type: 'transfer',
              description: entry.title
            };
          }
        },
        'advance': {
          dialogId: '#editTransferDialog',
          formId: '#editTransferForm',
          idField: 'transfer_id',
          getFormData: (entry) => {
            const familyNames = extractFamilyNamesFromArrow(entry.meta);
            const fromFamilyId = familyNames.from ? findFamilyIdByName(familyNames.from) : null;
            const toFamilyId = familyNames.to ? findFamilyIdByName(familyNames.to) : null;
            
            return {
              from_family_id: fromFamilyId || (state.families.length > 0 ? state.families[0].id : '1'),
              to_family_id: toFamilyId || (state.families.length > 0 ? state.families[0].id : '1'),
              amount: (entry.amount_minor / 100).toFixed(2),
              transfer_type: 'advance',
              description: entry.title
            };
          }
        },
        'loan': {
          dialogId: '#editLoanDialog',
          formId: '#editLoanForm',
          idField: 'loan_id',
          getFormData: (entry) => {
            const familyNames = extractFamilyNamesFromArrow(entry.meta);
            const borrowerFamilyId = familyNames.from ? findFamilyIdByName(familyNames.from) : null;
            const lenderFamilyId = familyNames.to ? findFamilyIdByName(familyNames.to) : null;
            
            return {
              lender_family_id: lenderFamilyId || (state.families.length > 0 ? state.families[0].id : '1'),
              borrower_family_id: borrowerFamilyId || (state.families.length > 0 ? state.families[0].id : '1'),
              amount: (entry.amount_minor / 100).toFixed(2),
              description: entry.title
            };
          }
        },
        'loan_repayment': {
          dialogId: null, // No edit for repayments
          formId: null,
          idField: null,
          getFormData: null
        }
      };
      
      const config = typeConfig[entryType];
      if (!config || !config.dialogId) return; // Skip unsupported types
      
      const dialog = qs(config.dialogId);
      const form = qs(config.formId);
      
      if (!dialog || !form) return;
      
      // Store entry data for later use
      const entryData = {
        id: entryId,
        type: entryType,
        element: timelineItem
      };
      
      // Set form ID field
      form.elements[config.idField].value = entryId;
      
      // Get entry from journal data
      const journalData = state.journal || [];
      const entry_full = journalData.find(
        (entry) =>
          String(entry.id) === String(entryId) &&
          String(entry.type) === String(entryType)
      );
      
      if (entry_full) {
        const formData = config.getFormData(entry_full);
        Object.keys(formData).forEach(key => {
          if (form.elements[key]) {
            if (key === 'split_method') {
              const radios = form.querySelectorAll(`input[name="${key}"]`);
              radios.forEach(radio => {
                radio.checked = radio.value === formData[key];
              });
            } else {
              form.elements[key].value = formData[key];
            }
          }
        });
        
        // Update custom category visibility for expense form
        if (entryType === 'expense') {
          const categorySelect = document.getElementById('editCategorySelect');
          const customCategoryLabel = document.getElementById('editCustomCategoryLabel');
          const customCategoryInput = document.getElementById('editCustomCategoryInput');
          
          if (categorySelect && customCategoryLabel && customCategoryInput) {
            // Trigger category change to show/hide custom category field
            if (categorySelect.value === 'Другое' && formData.custom_category) {
              customCategoryLabel.classList.remove('hidden');
              customCategoryInput.required = true;
            } else {
              customCategoryLabel.classList.add('hidden');
              customCategoryInput.required = false;
            }
          }
        }
      }
      
      dialog.showModal();
      syncSelectElements(); // Refresh family selects
      return;
    }
    
    // Click on loan card
    const loanCard = event.target.closest(".card[data-loan-id]");
    if (loanCard && !event.target.closest("button")) {
      openLoanEditor(loanCard.dataset.loanId);
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

    const removeTripUserButton = event.target.closest("[data-remove-trip-user]");
    if (removeTripUserButton) {
      const user = state.tripUsers.find(
        (item) => String(item.id) === String(removeTripUserButton.dataset.removeTripUser)
      );
      if (!user || !confirm(`Удалить доступ для "${user.username}"?`)) return;

      removeTripUser(state.tripId, user.id)
        .then(onDataChange)
        .then(() => toast("Доступ удален"))
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
  
  // Delete expense button
  qs("#deleteExpenseBtn")?.addEventListener("click", async () => {
    const form = qs("#editExpenseForm");
    const expenseId = form.elements.expense_id.value;
    
    if (!confirm("Удалить этот расход?")) return;
    
    try {
      await deleteExpense(state.tripId, expenseId);
      qs("#editExpenseDialog").close();
      form.reset();
      await onDataChange();
      toast("Расход удален");
    } catch (error) {
      toast(error.message);
    }
  });
  
  // Delete transfer button
  qs("#deleteTransferBtn")?.addEventListener("click", async () => {
    const form = qs("#editTransferForm");
    const transferId = form.elements.transfer_id.value;
    
    if (!confirm("Удалить этот перевод?")) return;
    
    try {
      await deleteTransfer(state.tripId, transferId);
      qs("#editTransferDialog").close();
      form.reset();
      await onDataChange();
      toast("Перевод удален");
    } catch (error) {
      toast(error.message);
    }
  });
  
  // Delete loan button
  qs("#deleteLoanBtn")?.addEventListener("click", async () => {
    const form = qs("#editLoanForm");
    const loanId = form.elements.loan_id.value;
    
    if (!confirm("Удалить этот заем?")) return;
    
    try {
      await deleteLoan(state.tripId, loanId);
      qs("#editLoanDialog").close();
      form.reset();
      await onDataChange();
      toast("Заем удален");
    } catch (error) {
      toast(error.message);
    }
  });
}

function openLoanEditor(loanId) {
  const loans = state.loans || [];
  const loan = loans.find(l => String(l.id) === String(loanId));
  
  if (!loan) return;
  
  const dialog = qs("#editLoanDialog");
  const form = qs("#editLoanForm");
  
  form.elements.loan_id.value = loanId;
  form.elements.amount.value = (loan.principal_amount_minor / 100).toFixed(2);
  form.elements.description.value = loan.description || '';
  form.elements.lender_family_id.value = loan.lender_family_id;
  form.elements.borrower_family_id.value = loan.borrower_family_id;
  
  dialog.showModal();
  syncSelectElements();
}

function syncFamilySelectPair(select, formSelector, firstName, secondName) {
  const form = qs(formSelector);
  if (!form?.contains(select)) return;

  keepFamilySelectsDifferent(form, firstName, secondName, select.name);
}

/**
 * Handle category selection and custom category input
 */
function setupCategoryHandling() {
  const categorySelect = document.getElementById('categorySelect');
  const customCategoryLabel = document.getElementById('customCategoryLabel');
  const customCategoryInput = document.getElementById('customCategoryInput');
  const expenseForm = document.getElementById('expenseForm');
  
  if (!categorySelect || !customCategoryLabel || !customCategoryInput) return;
  
  // Toggle custom category input visibility
  function updateCategoryVisibility() {
    if (categorySelect.value === 'Другое') {
      customCategoryLabel.classList.remove('hidden');
      customCategoryInput.required = true;
    } else {
      customCategoryLabel.classList.add('hidden');
      customCategoryInput.required = false;
      customCategoryInput.value = '';
    }
  }
  
  // Initialize visibility
  updateCategoryVisibility();
  
  // Listen for category changes
  categorySelect.addEventListener('change', updateCategoryVisibility);
}

// Call setup on DOM ready
document.addEventListener('DOMContentLoaded', setupCategoryHandling);
