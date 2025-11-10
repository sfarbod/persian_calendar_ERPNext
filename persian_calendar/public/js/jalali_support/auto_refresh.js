// Auto-refresh functionality for Jalali Settings
// Wait for frappe to be available
(function() {
  function initAutoRefresh() {
    if (typeof frappe !== 'undefined' && frappe.ui && frappe.ui.form) {
      // Listen for form events on Jalali Settings
      frappe.ui.form.on('Jalali Settings', {
        after_save: function(frm) {
          // Silently reload after save for Jalali Settings (no message)
          setTimeout(function() {
            window.location.reload();
          }, 100);
        }
      });
    } else {
      // Retry after a short delay
      setTimeout(initAutoRefresh, 100);
    }
  }

  // Start initialization
  initAutoRefresh();
})();
