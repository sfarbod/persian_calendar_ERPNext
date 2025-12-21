(function() {
  frappe.provide("frappe.ui.form");

  console.log("jalali_support script loaded");

  // Global variables - will be populated asynchronously
  let jalaliEnabled = null; // null = not checked yet, true/false = checked
  let EFFECTIVE_CALENDAR = {
    display_calendar: "Jalali",
    week_start: 6,
    week_end: 5
  };
  let FIRST_DAY = 6;
  
  // Cache for calendar settings to avoid multiple API calls
  let calendarSettingsCache = null;
  let calendarSettingsPromise = null;

  // Function to get calendar settings (with caching)
  async function getCalendarSettings() {
    if (calendarSettingsCache !== null) {
      return calendarSettingsCache;
    }
    
    if (calendarSettingsPromise) {
      return calendarSettingsPromise;
    }
    
    calendarSettingsPromise = (async () => {
      try {
        // Check if Jalali calendar is enabled
        const result = await frappe.call({ method: "persian_calendar.jalali_support.api.is_jalali_enabled" });
        jalaliEnabled = result && result.message;
        console.log("Jalali calendar enabled:", jalaliEnabled);
        
        if (!jalaliEnabled) {
          calendarSettingsCache = { enabled: false, calendar: { display_calendar: "Gregorian" } };
          return calendarSettingsCache;
        }
        
        // Get effective calendar settings
        const r = await frappe.call({ method: "persian_calendar.jalali_support.api.get_effective_calendar" });
        if (r && r.message) {
          EFFECTIVE_CALENDAR = r.message;
          console.log("Effective calendar settings:", EFFECTIVE_CALENDAR);
        }
        
        FIRST_DAY = EFFECTIVE_CALENDAR.week_start || 6;
        
        calendarSettingsCache = { 
          enabled: jalaliEnabled, 
          calendar: EFFECTIVE_CALENDAR,
          firstDay: FIRST_DAY
        };
        return calendarSettingsCache;
      } catch(e) {
        console.log("Error fetching calendar settings:", e);
        jalaliEnabled = false;
        calendarSettingsCache = { enabled: false, calendar: { display_calendar: "Gregorian" } };
        return calendarSettingsCache;
      }
    })();
    
    return calendarSettingsPromise;
  }

  // Start loading calendar settings immediately (but don't wait)
  getCalendarSettings();

  // Helper functions
  function gToJ(gDate) {
    // Check if toJalali is available (from jalaali.js)
    if (typeof toJalali === 'undefined' && typeof window.toJalali !== 'undefined') {
      window.toJalali = window.toJalali;
    }
    if (typeof toJalali === 'undefined') {
      console.error("toJalali function is not available! Make sure jalaali.js is loaded.");
      // Fallback: return a dummy object
      return { jy: 1400, jm: 1, jd: 1 };
    }
    return toJalali(gDate.getFullYear(), gDate.getMonth() + 1, gDate.getDate());
  }

  function jToG(jy, jm, jd) {
    // Check if toGregorian is available (from jalaali.js)
    if (typeof toGregorian === 'undefined' && typeof window.toGregorian !== 'undefined') {
      window.toGregorian = window.toGregorian;
    }
    if (typeof toGregorian === 'undefined') {
      console.error("toGregorian function is not available! Make sure jalaali.js is loaded.");
      // Fallback: return a dummy object
      return { gy: 2021, gm: 1, gd: 1 };
    }
    return toGregorian(jy, jm, jd);
  }

  function formatJalaliDate(jy, jm, jd) {
    return `${jy}-${String(jm).padStart(2,"0")}-${String(jd).padStart(2,"0")}`;
  }

  function parseJalaliDate(dateStr) {
    const parts = dateStr.split('-').map(Number);
    if (parts.length !== 3) return null;
    return { jy: parts[0], jm: parts[1], jd: parts[2] };
  }

// Global function to close all Jalali datepickers
function closeAllJalaliDatepickers() {
  $('.jalali-datepicker').each(function() {
    const $calendar = $(this);
    const instance = $calendar.data('jalaliDatepickerInstance');
    if (instance && instance.isOpen) {
      instance.close(); // Call the instance's close method to clean up its listeners
    } else {
      $calendar.hide(); // Fallback if instance not found or not open
    }
  });
  
  // No need to remove global handlers here if each instance manages its own
  // The keydown handler is now instance-specific, so no global off needed here.
  
  console.log('All Jalali datepickers closed');
}

// Enhanced Jalali Datepicker Class
class JalaliDatepicker {
    constructor(input, controlDate = null) {
      this.input = input;
      this.$input = $(input);
      this.controlDate = controlDate;
      this.isOpen = false;
      this.currentDate = gToJ(new Date());
      this.selectedDate = null;
      this.view = 'days'; // 'days', 'months', 'years'
      this.yearRange = { start: 1400, end: 1410 };
      
      this.init();
    }

    init() {
      this.createCalendar();
      this.bindEvents();
      this.updateDisplay();
      this.fixAlignment();
      this.$calendar.data('jalaliDatepickerInstance', this); // Store instance
    }
    
    fixAlignment() {
      // Ensure input field alignment matches other form fields using exact Frappe CSS variables
      const $input = this.$input;
      const $wrapper = $input.closest('.form-group, .frappe-control');
      const $formColumn = $input.closest('.form-column');
      
      if ($wrapper.length) {
        // Reset wrapper styles to match Frappe defaults with higher specificity
        $wrapper.css({
          'margin-bottom': '0 !important',
          'padding': '0 !important',
          'vertical-align': 'top !important',
          'display': 'block !important',
          'position': 'relative !important',
          'align-items': 'flex-start !important'
        });
        
        // Apply exact Frappe form control styling with higher specificity - match Gregorian exactly
        $input.css({
          'height': '28px !important', // Exact height like Gregorian
          'line-height': '28px !important', // Exact line-height like Gregorian
          'padding': '6px 8px !important', // Exact padding like Gregorian
          'margin': '0 !important',
          'vertical-align': 'top !important',
          'box-sizing': 'border-box !important',
          'background-color': '#fff !important', // Exact background like Gregorian
          'border': '1px solid #d1d8dd !important', // Exact border like Gregorian
          'border-radius': '4px !important', // Exact border-radius like Gregorian
          'font-size': '13px !important', // Exact font-size like Gregorian
          'font-weight': 'normal !important', // Exact font-weight like Gregorian
          'color': '#36414c !important', // Exact color like Gregorian
          'position': 'relative !important',
          'z-index': '1 !important',
          'display': 'block !important',
          'width': '100% !important',
          'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important' // Exact font-family like Gregorian
        });
        
        // Ensure the input container has proper positioning
        const $inputContainer = $input.closest('.control-input, .form-control-wrapper');
        if ($inputContainer.length) {
          $inputContainer.css({
            'position': 'relative !important',
            'display': 'block !important',
            'margin': '0 !important',
            'padding': '0 !important',
            'vertical-align': 'top !important',
            'align-items': 'flex-start !important'
          });
        }
        
        // Ensure form column alignment with higher specificity
        if ($formColumn.length) {
          $formColumn.css({
            'vertical-align': 'top !important',
            'display': 'flex !important',
            'flex-direction': 'column !important',
            'margin': '0 !important',
            'padding': '0 !important',
            'align-items': 'stretch !important',
            'justify-content': 'flex-start !important'
          });
        }
        
        // Target the specific form section to ensure proper alignment
        const $formSection = $input.closest('.form-section');
        if ($formSection.length) {
          $formSection.css({
            'display': 'flex !important',
            'flex-direction': 'row !important',
            'align-items': 'flex-start !important'
          });
        }
        
        // Ensure the datepicker doesn't affect layout
        if (this.$calendar && this.$calendar.length) {
          this.$calendar.css({
            'position': 'absolute !important',
            'z-index': '9999 !important',
            'margin': '0 !important',
            'padding': '0 !important'
          });
        }
      }
    }

    createCalendar() {
      // Remove existing calendar
      this.$input.siblings('.jalali-datepicker').remove();
      
      // Create calendar HTML with exact Gregorian styling
      const calendarHTML = `
        <div class="jalali-datepicker" style="
          position: absolute;
          top: 100%;
          left: 0;
          background: var(--bg-color, #fff);
          border: 1px solid var(--border-color, #d1d8dd);
          border-radius: var(--border-radius-sm, 6px);
          box-shadow: var(--shadow-md, 0 2px 8px rgba(0,0,0,0.15));
          z-index: 1000;
          display: none;
          width: 210px;
          padding: 1px;
          font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
          font-size: var(--text-sm, 13px);
          margin-top: 1px;
        ">
          <!-- Header with Navigation -->
          <div class="calendar-header" style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1px;
            padding-bottom: 1px;
            border-bottom: 1px solid var(--border-color, #e5e7eb);
          ">
            <button type="button" class="nav-btn prev-btn" style="
              background: transparent;
              border: none;
              cursor: pointer;
              padding: 1px 3px;
              font-size: 11px;
              color: var(--text-light, #6c7b7f);
              transition: color 0.2s ease;
              border-radius: 4px;
            ">‹</button>
            <button type="button" class="nav-btn prev-decade" style="
              background: transparent;
              border: none;
              cursor: pointer;
              padding: 1px 3px;
              font-size: 11px;
              color: #6c7b7f;
              transition: color 0.2s ease;
              border-radius: 4px;
            ">‹‹</button>
            <span class="month-year clickable" style="
              font-weight: 500;
              font-size: 12px;
              cursor: pointer;
              padding: 1px 4px;
              color: var(--text-color, #36414c);
              transition: background-color 0.2s ease;
              border-radius: 4px;
            "></span>
            <button type="button" class="nav-btn next-decade" style="
              background: transparent;
              border: none;
              cursor: pointer;
              padding: 1px 3px;
              font-size: 11px;
              color: #6c7b7f;
              transition: color 0.2s ease;
              border-radius: 4px;
            ">››</button>
            <button type="button" class="nav-btn next-btn" style="
              background: transparent;
              border: none;
              cursor: pointer;
              padding: 1px 3px;
              font-size: 11px;
              color: #6c7b7f;
              transition: color 0.2s ease;
              border-radius: 4px;
            ">›</button>
          </div>
          
          <!-- Content Area -->
          <div class="calendar-content">
            <!-- Days View -->
            <div class="days-view">
              <div class="weekdays" style="
                display: grid;
                grid-template-columns: repeat(7, 30px);
                gap: 0px;
                margin-bottom: 0px;
              "></div>
              <div class="days-grid" style="
                display: grid;
                grid-template-columns: repeat(7, 30px);
                gap: 0px;
              "></div>
            </div>
            
            <!-- Months View -->
            <div class="months-view" style="display: none;">
              <div class="months-grid" style="
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 1px;
                padding: 1px 0;
              "></div>
            </div>
            
            <!-- Years View -->
            <div class="years-view" style="display: none;">
              <div class="years-grid" style="
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 1px;
                padding: 1px 0;
              "></div>
            </div>
          </div>
          
          <!-- Footer -->
          <div class="calendar-footer" style="
            margin-top: 1px;
            padding-top: 1px;
            border-top: 1px solid var(--border-color, #eee);
            text-align: center;
          ">
            <button type="button" class="today-btn" style="
              background: transparent;
              color: var(--text-color, #36414c);
              border: 1px solid var(--border-color, #d1d8dd);
              padding: 2px 8px;
              border-radius: 3px;
              cursor: pointer;
              font-size: 12px;
              font-weight: normal;
              transition: all 0.2s ease;
              font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
              width: 100%;
            ">امروز</button>
          </div>
        </div>
      `;
      
      this.$calendar = $(calendarHTML);
      this.$input.after(this.$calendar);
      
      console.log("Jalali datepicker created");
    }

    bindEvents() {
      const self = this;
      
      // Input click
      this.$input.on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        self.toggle();
      });
      
      // Month/Year navigation
      this.$calendar.find('.prev-btn').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        self.navigateMonth(-1);
      });
      
      this.$calendar.find('.next-btn').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        self.navigateMonth(1);
      });
      
      // Month/Year click to switch views
      this.$calendar.find('.month-year').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        // Switch views based on current view
        if (self.view === 'days') {
          self.showMonthsView();
        } else if (self.view === 'months') {
          self.showYearsView();
        } else if (self.view === 'years') {
          self.showMonthsView();
        }
      });
      
      // Year navigation
      this.$calendar.find('.prev-decade').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        self.navigateYear(-10);
      });
      
      this.$calendar.find('.next-decade').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        self.navigateYear(10);
      });
      
      // Today button
      this.$calendar.find('.today-btn').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        self.selectToday();
      });
      
      // Simple click outside to close
      $(document).on('click.jalali-datepicker-global', function(e) {
        if (self.isOpen) {
          const $target = $(e.target);
          // Close if clicking outside the datepicker and not on the input field
          if (!$target.closest('.jalali-datepicker').length && 
              !$target.is(self.input)) {
            console.log('Closing datepicker due to click outside');
            self.close();
          }
        }
      });
      
      // Close when clicking on any date input field
      $(document).on('click.jalali-datepicker-date-inputs', function(e) {
        if (self.isOpen) {
          const $target = $(e.target);
          // Close if clicking on any date input field that's not our current input
          if ($target.is('input[data-fieldtype="Date"]') && 
              !$target.is(self.input)) {
            console.log('Closing datepicker due to click on another date field');
            self.close();
          }
        }
      });
      
      // ESC key to close - make it instance specific
      this._keydownHandler = function(e) {
        if (e.keyCode === 27 && self.isOpen) { // ESC
          self.close();
        }
      };
      $(document).on('keydown.jalali-datepicker-' + (this.input.id || 'default'), this._keydownHandler);

      // Use native event listener for capturing phase to ensure clicks outside are caught
      // This is more robust against e.stopPropagation() from other elements
      this._globalClickListener = function(e) {
        if (self.isOpen) {
          const $target = $(e.target);
          const isClickInsideDatepicker = $target.closest('.jalali-datepicker').length > 0;
          const isClickOnOwnInput = $target.is(self.input);

          if (!isClickInsideDatepicker && !isClickOnOwnInput) {
            console.log('Capturing phase: Closing datepicker due to click outside (general)');
            self.close();
          }
        }
      };
      document.addEventListener('click', this._globalClickListener, true); // true for capturing phase
      
      // Add hover effects
      this.$calendar.find('.nav-btn').hover(
        function() { $(this).css('background-color', '#f8f9fa'); },
        function() { $(this).css('background-color', 'transparent'); }
      );
      
      this.$calendar.find('.month-year').hover(
        function() { $(this).css('background-color', '#f8f9fa'); },
        function() { $(this).css('background-color', 'transparent'); }
      );
    }

    toggle() {
      if (this.isOpen) {
        this.close();
      } else {
        // Always reset to days view when opening
        this.view = 'days';
        this.open();
      }
    }

    open() {
      // Close all other Jalali datepickers first
      closeAllJalaliDatepickers();
      
      this.isOpen = true;
      this.view = 'days'; // Always reset to days view
      this.updateDisplay(); // Update display to show current date
      this.updateCalendar();
      this.$calendar.show();
      console.log("Calendar opened with view:", this.view);
    }

    close() {
      this.isOpen = false;
      this.$calendar.hide();
      
      // Remove event handlers to prevent memory leaks
      if (this._keydownHandler) {
        $(document).off('keydown.jalali-datepicker-' + (this.input.id || 'default'), this._keydownHandler);
        this._keydownHandler = null;
      }
      if (this._globalClickListener) {
        document.removeEventListener('click', this._globalClickListener, true);
        this._globalClickListener = null;
      }
      
      console.log("Calendar closed");
    }
    
    // Navigation methods
    navigateMonth(direction) {
      if (this.view === 'days') {
        this.currentDate.jm += direction;
        if (this.currentDate.jm > 12) {
          this.currentDate.jm = 1;
          this.currentDate.jy++;
        } else if (this.currentDate.jm < 1) {
          this.currentDate.jm = 12;
          this.currentDate.jy--;
        }
        this.updateCalendar();
      } else if (this.view === 'months') {
        // In months view, navigate year by year
        this.currentDate.jy += direction;
        this.updateMonthsView();
      }
    }
    
    navigateYear(direction) {
      // Navigate by decade (like Gregorian calendar)
      this.yearRange.start += direction;
      this.yearRange.end += direction;
      
      // Update current year to center of new range
      this.currentDate.jy = this.yearRange.start + 4; // Middle of decade
      
      this.updateYearsView();
    }
    
    // View switching methods
    showMonthsView() {
      this.view = 'months';
      this.updateMonthsView();
      this.$calendar.find('.days-view').hide();
      this.$calendar.find('.years-view').hide();
      this.$calendar.find('.months-view').show();
    }
    
    showYearsView() {
      this.view = 'years';
      this.updateYearsView();
      this.$calendar.find('.days-view').hide();
      this.$calendar.find('.months-view').hide();
      this.$calendar.find('.years-view').show();
    }
    
    showDaysView() {
      this.view = 'days';
      this.updateCalendar();
      this.$calendar.find('.months-view').hide();
      this.$calendar.find('.years-view').hide();
      this.$calendar.find('.days-view').show();
    }

    updateCalendar() {
      const monthNames = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 
                        'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
      
      // Update header
      this.$calendar.find('.month-year').text(`${monthNames[this.currentDate.jm - 1]} ${this.currentDate.jy}`);
      
      // Show/hide navigation buttons
      this.$calendar.find('.prev-btn, .next-btn').show();
      this.$calendar.find('.prev-decade, .next-decade').hide();
      
      // Hide all views first
      this.$calendar.find('.days-view').hide();
      this.$calendar.find('.months-view').hide();
      this.$calendar.find('.years-view').hide();
      
      // Show only the current view
      if (this.view === 'days') {
        this.$calendar.find('.days-view').show();
        // Update weekdays based on FIRST_DAY
        this.updateWeekdays();
        // Update days
        this.updateDays();
      } else if (this.view === 'months') {
        this.$calendar.find('.months-view').show();
        this.updateMonthsView();
      } else if (this.view === 'years') {
        this.$calendar.find('.years-view').show();
        this.updateYearsView();
      }
    }
    
    updateWeekdays() {
      // ترتیب صحیح روزهای هفته بر اساس تنظیمات: شنبه=6, یکشنبه=0, دوشنبه=1, سه‌شنبه=2, چهارشنبه=3, پنج‌شنبه=4, جمعه=5
      const weekdayNames = ['ی', 'د', 'س', 'چ', 'پ', 'ج', 'ش']; // [یکشنبه, دوشنبه, سه‌شنبه, چهارشنبه, پنج‌شنبه, جمعه, شنبه]
      const $weekdaysContainer = this.$calendar.find('.weekdays');
      $weekdaysContainer.empty();
      
      // با توجه به FIRST_DAY = 6 (شنبه)، ترتیب نمایش باید: شنبه, یکشنبه, دوشنبه, سه‌شنبه, چهارشنبه, پنج‌شنبه, جمعه
      for (let i = 0; i < 7; i++) {
        const dayIndex = (FIRST_DAY + i) % 7;
        $weekdaysContainer.append($(`<div class="weekday" style="text-align: center; padding: 0; font-weight: 500; font-size: 9px; color: var(--text-light, #7c7c7c); font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif); width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;">${weekdayNames[dayIndex]}</div>`));
      }
    }

    updateDays() {
      const $daysGrid = this.$calendar.find('.days-grid');
      $daysGrid.empty();
      
      const daysInMonth = this.currentDate.jm <= 6 ? 31 : 
                         (this.currentDate.jm <= 11 ? 30 : 
                         (this.currentDate.jy % 4 === 3 ? 30 : 29));
      
      // Get first day of month (Saturday = 0)
      const firstDay = this.getFirstDayOfMonth(this.currentDate.jy, this.currentDate.jm);
      
      // Calculate previous month's last days
      let prevMonth = this.currentDate.jm - 1;
      let prevYear = this.currentDate.jy;
      if (prevMonth < 1) {
        prevMonth = 12;
        prevYear--;
      }
      const prevMonthDays = prevMonth <= 6 ? 31 : 
                           (prevMonth <= 11 ? 30 : 
                           (prevYear % 4 === 3 ? 30 : 29));
      
      // Add previous month's last days (light color, selectable)
      for (let i = firstDay - 1; i >= 0; i--) {
        const day = prevMonthDays - i;
        const $prevDay = $(`<div class="day-cell prev-month-day" data-day="${day}" data-month="${prevMonth}" data-year="${prevYear}" style="
          text-align: center;
          padding: 0;
          cursor: pointer;
          border-radius: 0;
          transition: all 0.2s ease;
          font-size: 11px;
          color: var(--text-light, #999);
          width: 30px;
          height: 30px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
          border: none;
          background: transparent;
        ">${day}</div>`);
        
        // Add click handler for previous month days - select the day directly
        $prevDay.on('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.currentDate.jy = prevYear;
          this.currentDate.jm = prevMonth;
          this.currentDate.jd = day;
          this.selectDate(day);
        });
        
        // Add hover effect
        $prevDay.hover(
          function() { $(this).css('background-color', '#f8f9fa'); },
          function() { $(this).css('background-color', 'transparent'); }
        );
        
        $daysGrid.append($prevDay);
      }
      
      for (let day = 1; day <= daysInMonth; day++) {
        const $day = $(`<div class="day-cell" data-day="${day}" style="
          text-align: center;
          padding: 0;
          cursor: pointer;
          border-radius: 0;
          transition: all 0.2s ease;
          font-size: 11px;
          color: var(--text-color, #36414c);
          width: 30px;
          height: 30px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
          border: none;
          background: transparent;
        ">${day}</div>`);
        
        // Add click handler
        $day.on('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.selectDate(day);
        });
        
        // Add hover effects
        $day.hover(
          function() { 
            if (!$(this).hasClass('selected') && !$(this).hasClass('today')) {
              $(this).css('background-color', '#f8f9fa');
            }
          },
          function() { 
            if (!$(this).hasClass('selected') && !$(this).hasClass('today')) {
              $(this).css('background-color', 'transparent');
            }
          }
        );
        
        // Highlight today (gray background like Gregorian)
        const today = gToJ(new Date());
        if (this.currentDate.jy === today.jy && 
            this.currentDate.jm === today.jm && 
            day === today.jd) {
          $day.addClass('today').css({
            'background-color': 'var(--control-bg, #f3f3f3)',
            'color': 'var(--text-color, #36414c)',
            'font-weight': 'bold'
          });
        }
        
        // Highlight selected day (black background like Gregorian)
        if (this.selectedDate && 
            this.selectedDate.jy === this.currentDate.jy &&
            this.selectedDate.jm === this.currentDate.jm &&
            this.selectedDate.jd === day) {
          $day.addClass('selected').css({
            'background-color': 'var(--primary, #171717)',
            'color': 'var(--bg-color, white)',
            'font-weight': 'bold'
          });
        }
        
        $daysGrid.append($day);
      }
      
      // Calculate next month's first days
      let nextMonth = this.currentDate.jm + 1;
      let nextYear = this.currentDate.jy;
      if (nextMonth > 12) {
        nextMonth = 1;
        nextYear++;
      }
      
      // Calculate how many cells we need to fill to complete the grid (6 rows = 42 cells)
      const totalCells = 42; // 6 rows * 7 days
      const currentCells = firstDay + daysInMonth;
      const remainingCells = totalCells - currentCells;
      
      // Add next month's first days (light color, selectable)
      for (let day = 1; day <= remainingCells; day++) {
        const $nextDay = $(`<div class="day-cell next-month-day" data-day="${day}" data-month="${nextMonth}" data-year="${nextYear}" style="
          text-align: center;
          padding: 0;
          cursor: pointer;
          border-radius: 0;
          transition: all 0.2s ease;
          font-size: 11px;
          color: var(--text-light, #999);
          width: 30px;
          height: 30px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
          border: none;
          background: transparent;
        ">${day}</div>`);
        
        // Add click handler for next month days - select the day directly
        $nextDay.on('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.currentDate.jy = nextYear;
          this.currentDate.jm = nextMonth;
          this.currentDate.jd = day;
          this.selectDate(day);
        });
        
        // Add hover effect
        $nextDay.hover(
          function() { $(this).css('background-color', '#f8f9fa'); },
          function() { $(this).css('background-color', 'transparent'); }
        );
        
        $daysGrid.append($nextDay);
      }
      
      console.log(`Updated calendar with ${daysInMonth} days`);
    }

    selectDate(day) {
      this.selectedDate = {
        jy: this.currentDate.jy,
        jm: this.currentDate.jm,
        jd: day
      };
      
      const jalaliStr = formatJalaliDate(this.selectedDate.jy, this.selectedDate.jm, this.selectedDate.jd);
      
      // Convert to Gregorian for storage
      const gregorian = jToG(this.selectedDate.jy, this.selectedDate.jm, this.selectedDate.jd);
      const gregorianStr = `${gregorian.gy}-${String(gregorian.gm).padStart(2, '0')}-${String(gregorian.gd).padStart(2, '0')}`;
      
      console.log(`Converting Jalali ${jalaliStr} to Gregorian ${gregorianStr}`);
      
      // Set the Gregorian value in Frappe's system
      if (this.controlDate && this.controlDate.set_value) {
        this.controlDate.set_value(gregorianStr);
        this.$input.val(jalaliStr);
      } else {
        // Fallback: just set the input value
        this.$input.val(jalaliStr);
        this.$input.trigger('change');
      }
      
      this.close();
      console.log(`Selected date: ${jalaliStr} (${gregorianStr})`);
    }

    selectToday() {
      const today = gToJ(new Date());
      console.log('Today in Jalali:', today);
      
      // Update current date to today's month/year
      this.currentDate = { ...today };
      
      // Switch to days view to show the calendar properly
      this.view = 'days';
      
      // Update calendar display
      this.updateCalendar();
      
      // Select today's date
      this.selectDate(today.jd);
    }

    prevMonth() {
      if (this.currentDate.jm === 1) {
        this.currentDate.jm = 12;
        this.currentDate.jy--;
      } else {
        this.currentDate.jm--;
      }
      this.updateCalendar();
    }

    nextMonth() {
      if (this.currentDate.jm === 12) {
        this.currentDate.jm = 1;
        this.currentDate.jy++;
      } else {
        this.currentDate.jm++;
      }
      this.updateCalendar();
    }

    updateDisplay() {
      const value = this.$input.val();
      if (value) {
        const jalali = parseJalaliDate(value);
        if (jalali) {
          this.selectedDate = jalali;
          this.currentDate = { ...jalali };
        }
      }
      
      // Always reset to days view when updating display
      this.view = 'days';
    }
    
    // Month/Year view methods
    updateMonthsView() {
      // Update header to show only year
      this.$calendar.find('.month-year').text(`${this.currentDate.jy}`);
      
      // Hide/show navigation buttons - use year-by-year navigation for months view
      this.$calendar.find('.prev-btn, .next-btn').show();
      this.$calendar.find('.prev-decade, .next-decade').hide();
      
      const monthNames = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 
                        'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
      
      const $monthsGrid = this.$calendar.find('.months-grid');
      $monthsGrid.empty();
      
      monthNames.forEach((month, index) => {
        const $month = $(`<div class="month-cell" data-month="${index + 1}" style="
          text-align: center;
          padding: 3px 2px;
          cursor: pointer;
          border-radius: 0;
          transition: all 0.2s ease;
          font-size: 11px;
          color: var(--text-color, #36414c);
          border: 1px solid var(--border-color, #e2e2e2);
          font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
          background: transparent;
        ">${month}</div>`);
        
        // Add click handler
        $month.on('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.currentDate.jm = index + 1;
          this.showDaysView();
        });
        
        // Add hover effects
        $month.hover(
          function() { 
            if (!$(this).hasClass('selected')) {
              $(this).css('background-color', '#f8f9fa');
            }
          },
          function() { 
            if (!$(this).hasClass('selected')) {
              $(this).css('background-color', 'transparent');
            }
          }
        );
        
        // Check if current month - use site theme colors like Gregorian
        if (this.currentDate.jm === index + 1) {
          $month.addClass('selected').css({
            'background-color': 'var(--primary, #171717)',
            'color': 'var(--bg-color, white)',
            'font-weight': 'bold'
          });
        }
        
        $monthsGrid.append($month);
      });
    }
    
    updateYearsView() {
      // Calculate year range centered around current year (like Gregorian calendar)
      const currentYear = this.currentDate.jy;
      const startYear = Math.floor(currentYear / 10) * 10; // Round down to decade
      const endYear = startYear + 9;
      
      // Update yearRange for navigation
      this.yearRange = { start: startYear, end: endYear };
      
      // Update header to show year range
      this.$calendar.find('.month-year').text(`${this.yearRange.start} - ${this.yearRange.end}`);
      
      // Hide/show navigation buttons
      this.$calendar.find('.prev-btn, .next-btn').hide();
      this.$calendar.find('.prev-decade, .next-decade').show();
      
      const $yearsGrid = this.$calendar.find('.years-grid');
      $yearsGrid.empty();
      
      // Show years from startYear-1 to endYear+1 (like Gregorian calendar)
      for (let year = startYear - 1; year <= endYear + 1; year++) {
        const $year = $(`<div class="year-cell" data-year="${year}" style="
          text-align: center;
          padding: 3px 2px;
          cursor: pointer;
          border-radius: 0;
          transition: all 0.2s ease;
          font-size: 11px;
          color: var(--text-color, #36414c);
          border: 1px solid var(--border-color, #e2e2e2);
          font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
          background: transparent;
        ">${year}</div>`);
        
        // Add click handler
        $year.on('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.currentDate.jy = year;
          this.showMonthsView();
        });
        
        // Add hover effects
        $year.hover(
          function() { 
            if (!$(this).hasClass('selected')) {
              $(this).css('background-color', '#f8f9fa');
            }
          },
          function() { 
            if (!$(this).hasClass('selected')) {
              $(this).css('background-color', 'transparent');
            }
          }
        );
        
        // Check if current year - use site theme colors like Gregorian
        if (this.currentDate.jy === year) {
          $year.addClass('selected').css({
            'background-color': 'var(--primary, #171717) !important',
            'color': 'var(--bg-color, white) !important',
            'font-weight': 'bold !important'
          });
        }
        
        // Make years outside range faded (like Gregorian calendar)
        if (year < startYear || year > endYear) {
          $year.addClass('other-decade').css({
            'color': 'var(--text-light, #999) !important',
            'cursor': 'not-allowed !important',
            'opacity': '0.4 !important'
          });
          
          // Disable click for years outside range
          $year.off('click').on('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            // Do nothing for years outside range
          });
          
          // Remove hover effect for years outside range
          $year.off('mouseenter mouseleave');
        }
        
        $yearsGrid.append($year);
      }
    }
    
    getFirstDayOfMonth(year, month) {
      // Calculate first day of Jalali month
      // Convert Jalali date to Gregorian to get the weekday
      const gregorian = jToG(year, month, 1);
      const date = new Date(gregorian.gy, gregorian.gm - 1, gregorian.gd);
      
      // Convert JavaScript weekday (Sunday=0) to our weekday system (Saturday=0)
      // JavaScript: Sunday=0, Monday=1, Tuesday=2, Wednesday=3, Thursday=4, Friday=5, Saturday=6
      // Our system: Saturday=0, Sunday=1, Monday=2, Tuesday=3, Wednesday=4, Thursday=5, Friday=6
      const jsWeekday = date.getDay(); // 0=Sunday, 6=Saturday
      return (jsWeekday + 1) % 7; // Convert to our system: Saturday=0, Sunday=1, etc.
    }
  }

  // Override Frappe's ControlDate
  function overrideControlsWhenReady() {
    const hasControls = frappe && frappe.ui && frappe.ui.form && frappe.ui.form.ControlDate;
    if (!hasControls) {
      // Try again after a short delay
      setTimeout(overrideControlsWhenReady, 50);
      return;
    }

    // Check if already overridden
    if (frappe.ui.form.ControlDate.prototype.replaceWithJalaliDatepicker) {
      console.log("ControlDate already patched for Jalali");
      return;
    }

    const BaseControlDate = frappe.ui.form.ControlDate;

    class JalaliControlDate extends BaseControlDate {
      make_input() {
        // Always call parent first to get standard Frappe input structure
        super.make_input();
        
        // Check if we should use Jalali datepicker
        // If cache is not loaded yet, assume Jalali is enabled (default behavior)
        let useJalali = true;
        let display_calendar = "Jalali";
        
        if (calendarSettingsCache !== null) {
          // Settings are loaded - check them
          useJalali = calendarSettingsCache.enabled && 
                     calendarSettingsCache.calendar?.display_calendar !== "Gregorian";
          display_calendar = calendarSettingsCache.calendar?.display_calendar || "Jalali";
          
          // Update globals
          if (calendarSettingsCache.calendar) {
            EFFECTIVE_CALENDAR = calendarSettingsCache.calendar;
          }
          if (calendarSettingsCache.firstDay !== undefined) {
            FIRST_DAY = calendarSettingsCache.firstDay;
          }
        } else {
          // Settings not loaded yet - start loading in background
          // For now, use Jalali by default (will be corrected if needed)
          getCalendarSettings().then(settings => {
            // If settings show Gregorian, we need to switch to Gregorian
            if (!settings.enabled || settings.calendar?.display_calendar === "Gregorian") {
              // Remove Jalali datepicker and reinitialize with Gregorian
              if (this.jalaliDatepicker) {
                this.removeAirDatepickerInstances();
                this.jalaliDatepicker = null;
                // Reinitialize with Gregorian
                super.make_input();
              }
            } else {
              // Update globals
              if (settings.calendar) {
                EFFECTIVE_CALENDAR = settings.calendar;
              }
              if (settings.firstDay !== undefined) {
                FIRST_DAY = settings.firstDay;
              }
              // Update datepicker if it exists
              if (this.jalaliDatepicker) {
                this.jalaliDatepicker.updateDisplay();
              }
            }
          });
        }
        
        // Store display_calendar for later use
        this.display_calendar = display_calendar;
        
        // Replace the air-datepicker with our Jalali datepicker (if enabled)
        if (useJalali) {
          this.replaceWithJalaliDatepicker();
        }
      }
      
      replaceWithJalaliDatepicker() {
        // Find the input element
        this.$input = this.$wrapper.find('input');
        if (!this.$input.length) {
          this.$input = $(`<input class="form-control" type="text">`);
          this.$wrapper.append(this.$input);
        }
        
        // Remove any existing air-datepicker instances
        this.removeAirDatepickerInstances();
        
        // Remove any air-datepicker-related attributes and classes
        this.$input.removeAttr('data-date-format');
        this.$input.removeAttr('data-alt-input');
        this.$input.removeAttr('data-alt-format');
        this.$input.removeClass('datepicker-input');
        this.$input.removeClass('hasDatepicker');
        
        // Make input editable for better UX
        this.$input.attr('readonly', false);
        
        // Apply exact Frappe form control styling to match other fields with higher specificity
        this.$input.css({
          'height': 'var(--input-height) !important', // 28px
          'line-height': 'var(--input-height) !important', // 28px
          'padding': 'var(--input-padding) !important', // 6px 8px
          'margin': '0 !important',
          'vertical-align': 'top !important',
          'box-sizing': 'border-box !important',
          'background-color': 'var(--control-bg) !important',
          'border': '1px solid var(--border-color) !important',
          'border-radius': 'var(--border-radius-sm) !important',
          'font-size': 'var(--text-base) !important',
          'font-weight': 'var(--font-weight-regular) !important',
          'color': 'var(--text-color) !important',
          'position': 'relative !important',
          'z-index': '1 !important',
          'display': 'block !important',
          'width': '100% !important'
        });
        
        // Fix the control-input-wrapper to match other fields
        const $controlInputWrapper = this.$wrapper.find('.control-input-wrapper');
        if ($controlInputWrapper.length) {
          $controlInputWrapper.css({
            'margin': '0 !important',
            'padding': '0 !important',
            'vertical-align': 'top !important',
            'display': 'block !important',
            'position': 'relative !important'
          });
        }
        
        // Fix the control-input to match other fields
        const $controlInput = this.$wrapper.find('.control-input');
        if ($controlInput.length) {
          $controlInput.css({
            'margin': '0 !important',
            'padding': '0 !important',
            'vertical-align': 'top !important',
            'display': 'block !important',
            'position': 'relative !important',
            'height': 'var(--input-height) !important',
            'line-height': 'var(--input-height) !important'
          });
        }
        
        // Ensure wrapper styling matches other fields with higher specificity
        this.$wrapper.css({
          'margin': '0 !important',
          'padding': '0 !important',
          'vertical-align': 'top !important',
          'display': 'block !important',
          'position': 'relative !important',
          'align-items': 'flex-start !important'
        });
        
        // Ensure form column alignment with higher specificity
        const $formColumn = this.$input.closest('.form-column');
        if ($formColumn.length) {
          $formColumn.css({
            'vertical-align': 'top !important',
            'display': 'flex !important',
            'flex-direction': 'column !important',
            'margin': '0 !important',
            'padding': '0 !important',
            'align-items': 'stretch !important',
            'justify-content': 'flex-start !important'
          });
        }
        
        // Target the specific form section to ensure proper alignment
        const $formSection = this.$input.closest('.form-section');
        if ($formSection.length) {
          $formSection.css({
            'display': 'flex !important',
            'flex-direction': 'row !important',
            'align-items': 'flex-start !important'
          });
        }
        
        // Remove any existing air-datepicker instances
        this.removeAirDatepickerInstances();
        
        // Create Jalali datepicker
        this.jalaliDatepicker = new JalaliDatepicker(this.$input[0], this);
        
        // Fix alignment after datepicker creation
        this.fixFieldAlignment();
      }
      
      fixFieldAlignment() {
        // Ensure the entire field structure matches other fields
        const $formGroup = this.$wrapper.find('.form-group');
        if ($formGroup.length) {
          $formGroup.css({
            'margin-bottom': '0 !important',
            'padding': '0 !important',
            'vertical-align': 'top !important',
            'display': 'block !important'
          });
        }
        
        // Ensure the clearfix div doesn't affect alignment
        const $clearfix = this.$wrapper.find('.clearfix');
        if ($clearfix.length) {
          $clearfix.css({
            'margin': '0 !important',
            'padding': '0 !important',
            'vertical-align': 'top !important',
            'display': 'block !important'
          });
        }
        
        // Ensure the control-label doesn't affect alignment
        const $controlLabel = this.$wrapper.find('.control-label');
        if ($controlLabel.length) {
          $controlLabel.css({
            'margin': '0 !important',
            'padding': '0 !important',
            'vertical-align': 'top !important',
            'display': 'block !important',
            'line-height': 'normal !important'
          });
        }
        
        // Ensure the help span doesn't affect alignment
        const $help = this.$wrapper.find('.help');
        if ($help.length) {
          $help.css({
            'margin': '0 !important',
            'padding': '0 !important',
            'vertical-align': 'top !important',
            'display': 'block !important'
          });
        }
        
        // Ensure the help-box doesn't affect alignment
        const $helpBox = this.$wrapper.find('.help-box');
        if ($helpBox.length) {
          $helpBox.css({
            'margin': '0 !important',
            'padding': '0 !important',
            'vertical-align': 'top !important',
            'display': 'block !important'
          });
        }
      }
      
      removeAirDatepickerInstances() {
        // Remove any existing air-datepicker instances
        if (this.datepicker) {
          try {
            this.datepicker.destroy();
            this.datepicker = null;
          } catch(e) {
            console.log('Error destroying air-datepicker:', e);
          }
        }
        
        // Remove air-datepicker-related DOM elements
        $('.air-datepicker').remove();
        $('.datepicker-input').removeClass('datepicker-input');
        $('.hasDatepicker').removeClass('hasDatepicker');
        
        // Remove any datepicker icons or buttons
        $('.datepicker-icon').remove();
        $('.datepicker-btn').remove();
        
        // Clear any datepicker-related data
        if (this.$input && this.$input.length) {
          this.$input.removeData('datepicker');
        }
        
        // Remove any air-datepicker event listeners
        if (this.$input && this.$input.length) {
          this.$input.off('.datepicker');
        }
        
        console.log('Air-datepicker instances removed for field:', this.df.fieldname);
      }

      set_formatted_input(value) {
        try {
          // Check cache first
          const useJalali = calendarSettingsCache === null || 
                           (calendarSettingsCache.enabled && 
                            calendarSettingsCache.calendar?.display_calendar !== "Gregorian");
          
          // Check display calendar from instance, cache, or global
          let display_calendar = this.display_calendar;
          if (!display_calendar) {
            if (calendarSettingsCache && calendarSettingsCache.calendar) {
              display_calendar = calendarSettingsCache.calendar.display_calendar;
            } else {
              display_calendar = (EFFECTIVE_CALENDAR && EFFECTIVE_CALENDAR.display_calendar) || "Jalali";
            }
          }
          
          // Check if we should use Gregorian calendar (no conversion)
          if (!useJalali || display_calendar === "Gregorian") {
            // Use default Frappe behavior - show Gregorian dates as-is
            // Don't convert to Jalali
            console.log('set_formatted_input - Using Gregorian calendar, no conversion');
            return super.set_formatted_input(value);
          }

          // Jalali calendar - convert Gregorian to Jalali for display
          const r = super.set_formatted_input(value);

          // Convert Gregorian to Jalali for display (only when Jalali is enabled)
          if (value) {
            console.log('set_formatted_input - Input value:', value, 'Display calendar:', display_calendar);
            
            // Parse the date more carefully
            let gregorianDate;
            if (typeof value === 'string') {
              // Handle different date formats
              if (value.includes('T')) {
                gregorianDate = new Date(value);
              } else if (value.includes('-')) {
                gregorianDate = new Date(value + 'T00:00:00');
              } else {
                gregorianDate = new Date(value);
              }
            } else {
              gregorianDate = new Date(value);
            }
            
            console.log('set_formatted_input - Parsed date:', gregorianDate);
            
            if (!isNaN(gregorianDate.getTime())) {
              const jalali = gToJ(gregorianDate);
              const jalaliStr = formatJalaliDate(jalali.jy, jalali.jm, jalali.jd);
              console.log('set_formatted_input - Jalali:', jalali, 'String:', jalaliStr);
              this.$input.val(jalaliStr);
              
              // Update datepicker
              if (this.jalaliDatepicker) {
                this.jalaliDatepicker.updateDisplay();
              }
            } else {
              console.log('set_formatted_input - Invalid date, keeping original value');
            }
          }

          return r;
        } catch(e) {
          console.log('set_formatted_input error:', e);
          return super.set_formatted_input(value);
        }
      }
    }

    frappe.ui.form.ControlDate = JalaliControlDate;
    console.log("ControlDate patched for Jalali");
  }

  // Function to remove all existing air-datepicker instances from the page
  function removeAllAirDatepickerInstances() {
    // Remove all air-datepicker calendars
    $('.air-datepicker').remove();
    
    // Remove air-datepicker classes and attributes from all inputs
    $('input.datepicker-input, input.hasDatepicker').each(function() {
      $(this).removeClass('datepicker-input hasDatepicker');
      $(this).removeAttr('data-date-format');
      $(this).removeAttr('data-alt-input');
      $(this).removeAttr('data-alt-format');
      $(this).removeData('datepicker');
      
      // Remove event listeners
      $(this).off('.datepicker');
    });
    
    // Remove any datepicker icons or buttons
    $('.datepicker-icon, .datepicker-btn').remove();
    
    // Remove any air-datepicker instances from global scope
    if (window.Datepicker) {
      try {
        // Try to destroy all instances
        Object.keys(window.Datepicker.instances || {}).forEach(key => {
          try {
            window.Datepicker.instances[key].destroy();
          } catch(e) {
            console.log('Error destroying air-datepicker instance:', e);
          }
        });
      } catch(e) {
        console.log('Error accessing air-datepicker instances:', e);
      }
    }
    
    console.log('Removed all air-datepicker instances from the page');
  }
  
  // Remove existing air-datepicker instances immediately
  removeAllAirDatepickerInstances();
  
  // Also remove them periodically to catch any dynamically created ones
  setInterval(removeAllAirDatepickerInstances, 1000);

  // Start overriding
  overrideControlsWhenReady();

  // Override Fiscal Year defaults to Jalali year boundaries when enabled
  try {
    frappe.ui.form.on('Fiscal Year', {
      onload: async function(frm) {
        try {
          if (!frm.doc.__islocal) return; // only for new docs
          
          // Get calendar settings
          const settings = await getCalendarSettings();
          if (!settings.enabled) return;
          if (settings.calendar && settings.calendar.display_calendar === 'Gregorian') return;

          // If user already set a start date, don't override
          if (frm.doc.year_start_date) return;

          // Determine current Jalali year from today
          const todayG = new Date();
          const todayJ = gToJ(todayG);

          const jy = todayJ.jy;
          // Start: jy-01-01 (Jalali) => Gregorian
          const startG = jToG(jy, 1, 1);
          const startStr = `${startG.gy}-${String(startG.gm).padStart(2,'0')}-${String(startG.gd).padStart(2,'0')}`;

          // End: next jy's 01-01 minus one day
          const nextStartG = jToG(jy + 1, 1, 1);
          const nextStartDate = new Date(nextStartG.gy, nextStartG.gm - 1, nextStartG.gd);
          const endDate = new Date(nextStartDate.getTime() - 24 * 60 * 60 * 1000);
          const endStr = `${endDate.getFullYear()}-${String(endDate.getMonth()+1).padStart(2,'0')}-${String(endDate.getDate()).padStart(2,'0')}`;

          frm.set_value('year_start_date', startStr);
          // If not short year, Frappe's handler sets end automatically; force set to Jalali end regardless
          frm.set_value('year_end_date', endStr);
        } catch (e) {
          console.log('Error setting Jalali Fiscal Year defaults:', e);
        }
      }
    });
  } catch (e) {
    console.log('Unable to attach Fiscal Year onload override:', e);
  }

  // Listen for User form calendar_preference changes and refresh page after save
  // Only refresh if user is editing their own profile (My Settings)
  try {
    frappe.ui.form.on('User', {
      after_save: function(frm) {
        // Check if calendar_preference field exists and if user is editing their own profile
        if (frm.doc.calendar_preference !== undefined && 
            frm.doc.name === frappe.session.user) {
          console.log('User calendar_preference changed to:', frm.doc.calendar_preference);
          console.log('Reloading page to apply new calendar settings...');
          // Reload page to apply new calendar settings
          setTimeout(function() {
            window.location.reload();
          }, 500);
        }
      }
    });
  } catch (e) {
    console.log('Unable to attach User form handler:', e);
  }

})();