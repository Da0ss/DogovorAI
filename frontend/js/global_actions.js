/**
 * DogovorAI — Global Shared Actions and Handlers
 * Provides a robust submit wrapper to prevent app hangs,
 * and standard consent/terms checkbox synchronization.
 */

/**
 * Safe submission wrapper that catches all unhandled promise rejections,
 * alerts the user, and automatically resets common loading states to prevent UI hangs.
 * 
 * @param {Function} handler - The async submission/action handler.
 * @param {Event} event - The triggering DOM event.
 */
async function safeSubmit(handler, event) {
    if (event && typeof event.preventDefault === 'function') {
        event.preventDefault();
    }

    try {
        console.log("Triggering handler...");
        await handler(event);
    } catch (err) {
        console.error("Submission failed:", err);
        // Show user-friendly alert message
        alert("Произошла ошибка при загрузке. Попробуйте еще раз.");
    } finally {
        // Automatic global recovery of common loading states
        try {
            // 1. Hide any active spinners
            const spinners = document.querySelectorAll('.spinner, [id$="Spinner"], [id$="spinner"]');
            spinners.forEach(s => {
                s.style.display = 'none';
            });

            // 2. Reset loading buttons (remove loading classes, restore disabled status based on consent check)
            const termsConsent = document.getElementById('termsConsent');
            const isConsentChecked = termsConsent ? termsConsent.checked : true;

            const loadingButtons = document.querySelectorAll('.loading, button');
            loadingButtons.forEach(btn => {
                btn.classList.remove('loading');

                // If it's a register/oauth button and consent is NOT checked, keep it disabled.
                // Otherwise, if it was in a loading state, we enable it.
                if (termsConsent && !isConsentChecked && (btn.id === 'registerButton' || btn.id === 'googleRegisterBtn')) {
                    btn.setAttribute('disabled', 'disabled');
                    btn.classList.add('btn-locked');
                } else if (btn.classList.contains('loading') || btn.hasAttribute('data-was-loading')) {
                    btn.removeAttribute('disabled');
                    btn.classList.remove('btn-locked');
                }
            });

            // 3. Reset progress container / upload card display states on main app page
            const progressContainer = document.getElementById('progressContainer');
            const uploadCard = document.getElementById('uploadCard');
            if (progressContainer && uploadCard) {
                progressContainer.style.display = 'none';
                uploadCard.style.display = 'block';
            }
        } catch (recoveryErr) {
            console.error("Loader recovery failed:", recoveryErr);
        }
    }
}

/**
 * Initializes synchronization between a terms/consent checkbox and target action buttons.
 * 
 * @param {string} consentCheckboxId - The DOM ID of the checkbox.
 * @param {Array<string>} targetButtonIds - Array of DOM IDs of buttons to toggle.
 */
function initGlobalConsentToggle(consentCheckboxId, targetButtonIds) {
    const checkbox = document.getElementById(consentCheckboxId);
    if (!checkbox) {
        console.warn(`[ConsentToggle] Checkbox with ID "${consentCheckboxId}" not found.`);
        return;
    }

    const buttons = targetButtonIds.map(id => document.getElementById(id)).filter(btn => btn !== null);
    if (buttons.length === 0) {
        console.warn(`[ConsentToggle] No target buttons found for IDs:`, targetButtonIds);
        return;
    }

    function updateButtonStates() {
        const isChecked = checkbox.checked;
        buttons.forEach(btn => {
            if (isChecked) {
                btn.removeAttribute('disabled');
                btn.classList.remove('btn-locked');
            } else {
                btn.setAttribute('disabled', 'disabled');
                btn.classList.add('btn-locked');
            }
        });
    }

    // Set initial state based on checkbox check status
    updateButtonStates();

    // Listen for change events
    checkbox.addEventListener('change', updateButtonStates);
}

// Auto-enforce enctype="multipart/form-data" for any forms containing file inputs
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('form').forEach(form => {
        if (form.querySelector('input[type="file"]')) {
            form.setAttribute('enctype', 'multipart/form-data');
            console.log(`[FormEnforcer] Set enctype="multipart/form-data" for form:`, form.id || form);
        }
    });
});
