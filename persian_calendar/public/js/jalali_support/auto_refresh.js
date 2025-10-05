// Auto-refresh functionality for Jalali Settings
// Wait for frappe to be available
(function() {
  function initAutoRefresh() {
    if (typeof frappe !== 'undefined' && frappe.ui && frappe.ui.form) {
      // Listen for form events on Jalali Settings
      frappe.ui.form.on('Jalali Settings', {
        refresh: function(frm) {
          // Add custom save button behavior
          frm.page.add_inner_button(__('Save & Reload'), function() {
            frm.save().then(function() {
              // Show success message
              frappe.show_alert({
                message: __('تنظیمات ذخیره شد. صفحه در حال بارگذاری مجدد...'),
                indicator: 'green'
              });
              
              // Reload page after a short delay
              setTimeout(function() {
                window.location.reload();
              }, 1000);
            });
          });
        },

        after_save: function(frm) {
          console.log("Jalali Settings after_save triggered");
          
          // Always reload after save for Jalali Settings
          frappe.msgprint(__("تنظیمات تقویم جلالی ذخیره شد. صفحه در حال بارگذاری مجدد..."));
          setTimeout(function() {
            window.location.reload();
          }, 1500);
        },

        onload: function(frm) {
          console.log("Jalali Settings onload triggered");
          // Store original values for debugging
          if (!frm.is_new()) {
            console.log("Original values:", {
              enable_jalali: frm.doc.enable_jalali,
              default_calendar: frm.doc.default_calendar,
              computation_priority: frm.doc.computation_priority,
              week_start: frm.doc.week_start,
              week_end: frm.doc.week_end
            });
          }
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
