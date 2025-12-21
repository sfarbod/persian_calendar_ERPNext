(async function() {
  // Check if Jalali calendar is enabled
  let jalaliEnabled = false;
  
  try {
    const result = await frappe.call({ method: "persian_calendar.jalali_support.api.is_jalali_enabled" });
    jalaliEnabled = result && result.message;
    console.log("Jalali calendar enabled:", jalaliEnabled);
  } catch(e) {
    console.log("Error checking Jalali settings:", e);
    jalaliEnabled = false;
  }

  if (!jalaliEnabled) {
    console.log("Jalali calendar is disabled, skipping formatters");
    return;
  }

  // Get effective calendar settings
  let EFFECTIVE_CALENDAR = {
    display_calendar: "Jalali",
    week_start: 6,
    week_end: 5
  };
  
  try {
    const r = await frappe.call({ method: "persian_calendar.jalali_support.api.get_effective_calendar" });
    if (r && r.message) {
      EFFECTIVE_CALENDAR = r.message;
      console.log("Effective calendar settings in formatters:", EFFECTIVE_CALENDAR);
    }
  } catch(e) {
    console.log("Error fetching effective calendar in formatters:", e);
  }

  function g2j_str(value) {
    try {
      // Parse as UTC to avoid TZ shifts and month off-by-one
      const d = new Date(value + (value.length === 10 ? 'T00:00:00Z' : 'Z'));
      if (isNaN(d)) return value;
      const j = toJalali(d.getUTCFullYear(), d.getUTCMonth()+1, d.getUTCDate());
      return `${j.jy}-${String(j.jm).padStart(2,"0")}-${String(j.jd).padStart(2,"0")}`;
    } catch(e) {
      return value;
    }
  }

  // Helper function to check if we should convert to Jalali
  function shouldConvertToJalali() {
    return EFFECTIVE_CALENDAR && EFFECTIVE_CALENDAR.display_calendar === "Jalali";
  }

  // Global datetime helpers → force Jalali display in UI components (lists/reports)
  const dt = frappe.datetime;
  const orig_str_to_user = dt.str_to_user?.bind(dt);
  const orig_str_to_user_with_default = dt.str_to_user_with_default?.bind(dt);
  const orig_format_date = dt.format_date?.bind(dt);
  const orig_format_datetime = dt.format_datetime?.bind(dt);

  if (orig_str_to_user) {
    dt.str_to_user = function(value) {
      if (!value) return value;
      
      // Check if we should convert to Jalali
      if (!shouldConvertToJalali()) {
        // Use original function for Gregorian calendar
        return orig_str_to_user(value);
      }
      
      const is_datetime = typeof value === "string" && value.length > 10 && value.includes(":");
      if (is_datetime) {
        const date = value.slice(0, 10);
        const time = value.slice(11, 19);
        return `${g2j_str(date)} ${time}`.trim();
      }
      return g2j_str(value);
    };
  }
  if (orig_str_to_user_with_default) {
    dt.str_to_user_with_default = function(value) {
      if (!value) return value;
      
      // Check if we should convert to Jalali
      if (!shouldConvertToJalali()) {
        return orig_str_to_user_with_default(value);
      }
      
      return dt.str_to_user(value);
    };
  }
  if (orig_format_date) {
    dt.format_date = function(date_str) {
      // Check if we should convert to Jalali
      if (!shouldConvertToJalali()) {
        return orig_format_date(date_str);
      }
      return g2j_str(date_str);
    };
  }
  if (orig_format_datetime) {
    dt.format_datetime = function(value) {
      if (!value) return value;
      
      // Check if we should convert to Jalali
      if (!shouldConvertToJalali()) {
        return orig_format_datetime(value);
      }
      
      const date = value.slice(0, 10);
      const time = value.slice(11, 19) || "";
      return `${g2j_str(date)} ${time}`.trim();
    };
  }

  // Store original formatters
  const orig_date_formatter = frappe.form.formatters.date;
  const orig_datetime_formatter = frappe.form.formatters.datetime;

  frappe.form.formatters.date = function(value, df, options, doc) {
    if (!value) return value;
    
    // Check if we should convert to Jalali
    if (!shouldConvertToJalali()) {
      // Use original formatter for Gregorian calendar
      if (orig_date_formatter) {
        return orig_date_formatter(value, df, options, doc);
      }
      return value;
    }
    
    return g2j_str(value);
  };
  
  frappe.form.formatters.datetime = function(value, df, options, doc) {
    if (!value) return value;
    
    // Check if we should convert to Jalali
    if (!shouldConvertToJalali()) {
      // Use original formatter for Gregorian calendar
      if (orig_datetime_formatter) {
        return orig_datetime_formatter(value, df, options, doc);
      }
      return value;
    }
    
    const d = new Date(value);
    if (isNaN(d)) return value;
    const j = toJalali(d.getFullYear(), d.getMonth()+1, d.getDate());
    const time = value.slice(11, 19) || "";
    return `${j.jy}-${String(j.jm).padStart(2,"0")}-${String(j.jd).padStart(2,"0")} ${time}`;
  };
})();


