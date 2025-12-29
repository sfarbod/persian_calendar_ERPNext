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

  function formatJalaliDateTime(jy, jm, jd, hour, minute, second) {
    const dateStr = formatJalaliDate(jy, jm, jd);
    const timeStr = `${String(hour || 0).padStart(2,"0")}:${String(minute || 0).padStart(2,"0")}:${String(second || 0).padStart(2,"0")}`;
    return `${dateStr} ${timeStr}`;
  }

  function parseJalaliDate(dateStr) {
    const parts = dateStr.split('-').map(Number);
    if (parts.length !== 3) return null;
    return { jy: parts[0], jm: parts[1], jd: parts[2] };
  }

  function parseJalaliDateTime(dateTimeStr) {
    // Handle format: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD HH:MM"
    const spaceIndex = dateTimeStr.indexOf(' ');
    if (spaceIndex === -1) {
      // No time part, parse as date only
      return parseJalaliDate(dateTimeStr);
    }
    
    const dateStr = dateTimeStr.substring(0, spaceIndex);
    const timeStr = dateTimeStr.substring(spaceIndex + 1);
    const date = parseJalaliDate(dateStr);
    
    if (!date) return null;
    
    // Parse time: "HH:MM:SS" or "HH:MM"
    const timeParts = timeStr.split(':').map(Number);
    return {
      jy: date.jy,
      jm: date.jm,
      jd: date.jd,
      hour: timeParts[0] || 0,
      minute: timeParts[1] || 0,
      second: timeParts[2] || 0
    };
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
    constructor(input, controlDate = null, isDateTime = false) {
      this.input = input;
      this.$input = $(input);
      this.controlDate = controlDate;
      this.isDateTime = isDateTime;
      this.isOpen = false;
      this._isDraggingSlider = false; // Track if user is dragging a slider
      this._isApplyingValue = false; // Track if we're applying a value (prevent closing during updates)
      this.currentDate = gToJ(new Date());
      this.selectedDate = null;
      this.selectedTime = { hour: new Date().getHours(), minute: new Date().getMinutes(), second: new Date().getSeconds() };
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
      // Don't override any styling - let Frappe handle all layout and spacing
      // Only ensure the datepicker doesn't affect layout
        if (this.$calendar && this.$calendar.length) {
          this.$calendar.css({
            'position': 'absolute !important',
          'z-index': '9999 !important'
          });
      }
    }

    createCalendar() {
      // Remove existing calendar
      this.$input.siblings('.jalali-datepicker').remove();
      
      // Create calendar HTML with exact Gregorian styling
      const calendarHTML = `
        <div class="jalali-datepicker ${this.isDateTime ? 'jalali-datetime-picker' : ''}" style="
          position: absolute;
          top: 100%;
          left: 0;
          background: var(--bg-color, #fff);
          border: 1px solid var(--border-color, #d1d8dd);
          border-radius: var(--border-radius-sm, 6px);
          box-shadow: var(--shadow-md, 0 2px 8px rgba(0,0,0,0.15));
          z-index: 1000;
          display: none;
          width: ${this.isDateTime ? '240px' : '210px'};
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
          
          <!-- Time Picker (for datetime) -->
          ${this.isDateTime ? `
          <div class="time-picker" style="
            margin-top: 0;
            padding: 8px;
            border-top: 1px solid var(--border-color, #e5e7eb);
            background: var(--bg-color, #fafafa);
          ">
            <div style="display: flex; flex-direction: column; gap: 8px;">
              <!-- Hour -->
              <div style="display: flex; align-items: center; gap: 8px;">
                <label style="font-size: 11px; color: var(--text-color, #36414c); min-width: 30px;">ساعت:</label>
                <input type="range" class="time-hour" min="0" max="23" value="0" style="
                  flex: 1;
                  height: 4px;
                  background: var(--border-color, #d1d8dd);
                  border-radius: 2px;
                  outline: none;
                  -webkit-appearance: none;
                ">
                <span class="time-hour-value" style="font-size: 11px; color: var(--text-color, #36414c); min-width: 25px; text-align: center; font-weight: 500;">0</span>
              </div>
              <!-- Minute -->
              <div style="display: flex; align-items: center; gap: 8px;">
                <label style="font-size: 11px; color: var(--text-color, #36414c); min-width: 30px;">دقیقه:</label>
                <input type="range" class="time-minute" min="0" max="59" value="0" style="
                  flex: 1;
                  height: 4px;
                  background: var(--border-color, #d1d8dd);
                  border-radius: 2px;
                  outline: none;
                  -webkit-appearance: none;
                ">
                <span class="time-minute-value" style="font-size: 11px; color: var(--text-color, #36414c); min-width: 25px; text-align: center; font-weight: 500;">0</span>
              </div>
              <!-- Second -->
              <div style="display: flex; align-items: center; gap: 8px;">
                <label style="font-size: 11px; color: var(--text-color, #36414c); min-width: 30px;">ثانیه:</label>
                <input type="range" class="time-second" min="0" max="59" value="0" style="
                  flex: 1;
                  height: 4px;
                  background: var(--border-color, #d1d8dd);
                  border-radius: 2px;
                  outline: none;
                  -webkit-appearance: none;
                ">
                <span class="time-second-value" style="font-size: 11px; color: var(--text-color, #36414c); min-width: 25px; text-align: center; font-weight: 500;">0</span>
              </div>
            </div>
            <style>
              .jalali-datepicker .time-picker input[type="range"]::-webkit-slider-thumb {
                -webkit-appearance: none;
                appearance: none;
                width: 14px;
                height: 14px;
                background: var(--primary, #171717);
                border-radius: 50%;
                cursor: pointer;
              }
              .jalali-datepicker .time-picker input[type="range"]::-moz-range-thumb {
                width: 14px;
                height: 14px;
                background: var(--primary, #171717);
                border-radius: 50%;
                cursor: pointer;
                border: none;
              }
              .jalali-datepicker .time-picker input[type="range"]:hover::-webkit-slider-thumb {
                background: var(--primary, #000);
              }
              .jalali-datepicker .time-picker input[type="range"]:hover::-moz-range-thumb {
                background: var(--primary, #000);
              }
            </style>
          </div>
          ` : ''}
          
          <!-- Footer -->
          <div class="calendar-footer" style="
            margin-top: 1px;
            padding-top: 1px;
            border-top: 1px solid var(--border-color, #eee);
            text-align: center;
          ">
            <button type="button" class="${this.isDateTime ? 'now-btn' : 'today-btn'}" style="
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
            ">${this.isDateTime ? 'اکنون' : 'امروز'}</button>
          </div>
        </div>
      `;
      
      this.$calendar = $(calendarHTML);
      this.$input.after(this.$calendar);
      
      console.log("Jalali datepicker created");
    }

    bindEvents() {
      const self = this;
      
      // Input click - toggle calendar (open if closed, close if open)
      // Use mousedown instead of click to prevent _globalClickListener from closing it immediately
      this.$input.on('mousedown', function(e) {
        e.stopPropagation();
        // Use setTimeout to ensure this runs before _globalClickListener
        setTimeout(function() {
          if (self.isOpen) {
            // If already open, close it
            self.close();
          } else {
            // If closed, open it
            self.open();
          }
        }, 0);
      });
      
      // Also handle focus for better compatibility
      this.$input.on('focus', function(e) {
        e.stopPropagation();
        // Use setTimeout to ensure this runs before _globalClickListener
        setTimeout(function() {
          if (!self.isOpen) {
            // Only open if not already open (don't toggle on focus)
            self.open();
          }
        }, 0);
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
      
      // Today/Now button
      this.$calendar.find('.today-btn, .now-btn').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        if (self.isDateTime) {
          self.selectNow();
        } else {
          self.selectToday();
        }
      });
      
      // Time picker sliders (for datetime)
      if (this.isDateTime) {
        const updateTime = function() {
          const hour = parseInt(self.$calendar.find('.time-hour').val()) || 0;
          const minute = parseInt(self.$calendar.find('.time-minute').val()) || 0;
          const second = parseInt(self.$calendar.find('.time-second').val()) || 0;
          
          // Update value labels
          self.$calendar.find('.time-hour-value').text(hour);
          self.$calendar.find('.time-minute-value').text(minute);
          self.$calendar.find('.time-second-value').text(second);
          
          self.selectedTime = {
            hour: hour,
            minute: minute,
            second: second
          };
          // Apply the updated time if date is already selected
          // Use flag to prevent calendar from closing during update
          if (self.selectedDate) {
            // Set flag to prevent calendar from closing
            self._isApplyingValue = true;
            
            // Update input value but keep calendar open
            let jalaliStr = formatJalaliDateTime(
              self.selectedDate.jy, 
              self.selectedDate.jm, 
              self.selectedDate.jd,
              hour,
              minute,
              second
            );
            // Convert to Gregorian for storage
            const gregorian = jToG(self.selectedDate.jy, self.selectedDate.jm, self.selectedDate.jd);
            let gregorianStr = `${gregorian.gy}-${String(gregorian.gm).padStart(2, '0')}-${String(gregorian.gd).padStart(2, '0')}`;
            gregorianStr += ` ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:${String(second).padStart(2, '0')}`;
            
            // Set the value directly without closing calendar
            if (self.controlDate && self.controlDate.set_value) {
              self.controlDate.set_value(gregorianStr);
              self.$input.val(jalaliStr);
            } else {
              self.$input.val(jalaliStr);
              // Don't trigger change event as it might cause issues
              // self.$input.trigger('change');
            }
            
            // Clear flag after a delay
            setTimeout(function() {
              self._isApplyingValue = false;
            }, 200);
          }
        };
        
        // Update on input (while dragging) and change (on release)
        // Track if user is dragging to prevent calendar from closing
        const timePickerSliders = this.$calendar.find('.time-hour, .time-minute, .time-second');
        
        // Mark dragging when user starts dragging (use instance variable)
        timePickerSliders.on('mousedown', function(e) {
          self._isDraggingSlider = true;
          // Don't stop propagation - needed for slider to work
        });
        
        // Clear dragging flag when mouse is released
        timePickerSliders.on('mouseup', function(e) {
          // Clear flag after a delay to allow click event to be handled
          setTimeout(function() {
            self._isDraggingSlider = false;
          }, 300);
          // Don't stop propagation
        });
        
        // Stop click events on sliders (but check if dragging first)
        timePickerSliders.on('click', function(e) {
          if (self._isDraggingSlider) {
            // If we were dragging, this click is from the drag, ignore it completely
            e.stopPropagation();
            e.preventDefault();
            self._isDraggingSlider = false;
            return false;
          }
          // Normal click (not from drag), stop propagation
          e.stopPropagation();
        });
        
        // Update time during drag - keep dragging flag true
        timePickerSliders.on('input', function(e) {
          self._isDraggingSlider = true; // Keep flag true during drag
          updateTime();
        });
        
        // Update time after drag ends
        timePickerSliders.on('change', function(e) {
          setTimeout(function() {
            self._isDraggingSlider = false;
          }, 300);
          updateTime();
        });
        
        // Stop click events on time-picker container
        const $timePicker = this.$calendar.find('.time-picker');
        $timePicker.on('click', function(e) {
          e.stopPropagation();
        });
      }
      
      // Simple click outside to close - removed, using _globalClickListener instead
      // This was causing conflicts with slider interactions
      
      // Close when clicking on any date/datetime input field
      $(document).on('click.jalali-datepicker-date-inputs', function(e) {
        if (self.isOpen) {
          const $target = $(e.target);
          // Close if clicking on any date/datetime input field that's not our current input
          if (($target.is('input[data-fieldtype="Date"]') || $target.is('input[data-fieldtype="Datetime"]')) && 
              !$target.is(self.input)) {
            console.log('Closing datepicker due to click on another date/datetime field');
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

      // Flag to prevent closing during value updates
      this._isApplyingValue = false;
      
      // Simple click outside to close
      // Use setTimeout to allow slider drag events to complete first
      this._globalClickListener = function(e) {
        if (!self.isOpen) {
          // Calendar is not open, ignore
          return;
        }
        
        // Check immediately if click is on input (before any other checks)
        const $target = $(e.target);
        const isClickOnOwnInput = $target.is(self.input) || 
                                 $(self.input).find($target).length > 0 ||
                                 $target.closest(self.input).length > 0;
        
        // If clicking on input, don't close (input handler will handle toggle)
        if (isClickOnOwnInput) {
          return;
        }
        
        console.log(`_globalClickListener: click detected, _isApplyingValue=${self._isApplyingValue}, _isDraggingSlider=${self._isDraggingSlider}`);
        
        // If currently applying value or dragging slider, don't close
        if (self._isApplyingValue || self._isDraggingSlider) {
          console.log(`_globalClickListener: ignoring click (applying value or dragging)`);
          return;
        }
        
        // Check if click is inside calendar
        const isClickInsideDatepicker = self.$calendar && self.$calendar.length > 0 && 
                                       ($target.closest(self.$calendar).length > 0 || 
                                        self.$calendar.find($target).length > 0 ||
                                        $target.closest('.jalali-datepicker').length > 0);
        const isTimePickerElement = $target.closest('.time-picker').length > 0 ||
                                   $target.is('input[type="range"]') ||
                                   $target.closest('input[type="range"]').length > 0 ||
                                   $target.hasClass('time-hour') ||
                                   $target.hasClass('time-minute') ||
                                   $target.hasClass('time-second');
        
        // If clicking inside calendar or on slider, don't close
        if (isClickInsideDatepicker || isTimePickerElement) {
          console.log(`_globalClickListener: clicking inside calendar/slider, ignoring`);
          return;
        }
        
        // Use setTimeout to check after all other handlers have run
        // This allows slider drag events to complete before we check
        setTimeout(function() {
          // Check if calendar is still open (might have been closed by another event)
          if (!self.isOpen) {
            return;
          }
          
          console.log(`_globalClickListener (timeout): checking again, _isApplyingValue=${self._isApplyingValue}, _isDraggingSlider=${self._isDraggingSlider}`);
          
          // Check again if applying value or dragging (might have started during timeout)
          if (self._isApplyingValue || self._isDraggingSlider) {
            console.log(`_globalClickListener (timeout): ignoring click (applying value or dragging)`);
            return;
          }
          
          // Re-check if click is inside calendar (in case DOM changed)
          const $targetAgain = $(e.target);
          const isClickInsideDatepickerAgain = self.$calendar && self.$calendar.length > 0 && 
                                               ($targetAgain.closest(self.$calendar).length > 0 || 
                                                self.$calendar.find($targetAgain).length > 0 ||
                                                $targetAgain.closest('.jalali-datepicker').length > 0);
          const isClickOnOwnInputAgain = $targetAgain.is(self.input) || 
                                        $(self.input).find($targetAgain).length > 0 ||
                                        $targetAgain.closest(self.input).length > 0;
          const isTimePickerElementAgain = $targetAgain.closest('.time-picker').length > 0 ||
                                           $targetAgain.is('input[type="range"]') ||
                                           $targetAgain.closest('input[type="range"]').length > 0 ||
                                           $targetAgain.hasClass('time-hour') ||
                                           $targetAgain.hasClass('time-minute') ||
                                           $targetAgain.hasClass('time-second');
          
          // If clicking inside calendar, on input, or on slider, don't close
          if (isClickInsideDatepickerAgain || isClickOnOwnInputAgain || isTimePickerElementAgain) {
            console.log(`_globalClickListener (timeout): clicking inside calendar/input/slider, ignoring`);
            return;
          }
          
          // Click is outside, close the calendar
          console.log('_globalClickListener (timeout): Closing datepicker due to click outside');
          self.close();
        }, 100); // Reduced delay for better responsiveness
      };
      
      // Use click event (bubbling phase)
      document.addEventListener('click', this._globalClickListener, false);
      
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
      // Don't do anything if already open
      if (this.isOpen) {
        return;
      }
      
      // Close all other Jalali datepickers first (but not this one)
      const self = this;
      $('.jalali-datepicker').each(function() {
        const $calendar = $(this);
        const instance = $calendar.data('jalaliDatepickerInstance');
        if (instance && instance !== self && instance.isOpen) {
          instance.close();
        }
      });
      
      this.isOpen = true;
      this.view = 'days'; // Always reset to days view
      this.updateDisplay(); // Update display to show current date (this will also update time picker if datetime)
      this.updateCalendar();
      
      // Initialize time picker if datetime
      if (this.isDateTime && this.$calendar) {
        this.$calendar.find('.time-hour').val(this.selectedTime.hour);
        this.$calendar.find('.time-minute').val(this.selectedTime.minute);
        this.$calendar.find('.time-second').val(this.selectedTime.second);
        // Update value labels
        this.$calendar.find('.time-hour-value').text(this.selectedTime.hour);
        this.$calendar.find('.time-minute-value').text(this.selectedTime.minute);
        this.$calendar.find('.time-second-value').text(this.selectedTime.second);
      }
      
      this.$calendar.show();
      console.log("Calendar opened with view:", this.view, "isDateTime:", this.isDateTime);
    }

    close() {
      this.isOpen = false;
      this._isDraggingSlider = false; // Reset dragging flag
      this._isApplyingValue = false; // Reset applying value flag
      this.$calendar.hide();
      
      // Remove event handlers to prevent memory leaks
      if (this._keydownHandler) {
        $(document).off('keydown.jalali-datepicker-' + (this.input.id || 'default'), this._keydownHandler);
        this._keydownHandler = null;
      }
      if (this._globalClickListener) {
        document.removeEventListener('click', this._globalClickListener, false);
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

    selectDate(day, closeCalendar) {
      console.log(`selectDate called: day=${day}, closeCalendar=${closeCalendar}, isDateTime=${this.isDateTime}`);
      
      // For datetime fields, never auto-close calendar (allow time selection)
      // For date fields, close immediately if closeCalendar is true (default true for date fields)
      if (closeCalendar === undefined) {
        closeCalendar = !this.isDateTime; // Don't close for datetime, close for date
      }
      
      this.selectedDate = {
        jy: this.currentDate.jy,
        jm: this.currentDate.jm,
        jd: day
      };
      
      console.log(`selectDate: selectedDate set to:`, this.selectedDate);
      
      // Update time from time picker if datetime
      if (this.isDateTime) {
        this.selectedTime = {
          hour: parseInt(this.$calendar.find('.time-hour').val()) || this.selectedTime.hour || 0,
          minute: parseInt(this.$calendar.find('.time-minute').val()) || this.selectedTime.minute || 0,
          second: parseInt(this.$calendar.find('.time-second').val()) || this.selectedTime.second || 0
        };
        console.log(`selectDate: selectedTime set to:`, this.selectedTime);
      }
      
      // Apply value without closing calendar (for datetime, calendar stays open)
      console.log(`selectDate: calling applySelectedValue, isOpen=${this.isOpen}`);
      this.applySelectedValue();
      
      // For datetime fields, never auto-close calendar (allow time selection)
      // For date fields, close immediately
      if (!this.isDateTime && closeCalendar) {
        console.log(`selectDate: closing calendar (date field)`);
        this.close();
      } else {
        console.log(`selectDate: NOT closing calendar (datetime field or closeCalendar=false), isOpen=${this.isOpen}`);
      }
      
      console.log(`Selected ${this.isDateTime ? 'datetime' : 'date'}:`, this.selectedDate);
    }
    
    applySelectedValue() {
      console.log(`applySelectedValue called, isOpen=${this.isOpen}, _isApplyingValue=${this._isApplyingValue}`);
      
      // Set flag to prevent calendar from closing during value update
      this._isApplyingValue = true;
      console.log(`applySelectedValue: _isApplyingValue set to true`);
      
      let jalaliStr;
      if (this.isDateTime) {
        jalaliStr = formatJalaliDateTime(
          this.selectedDate.jy, 
          this.selectedDate.jm, 
          this.selectedDate.jd,
          this.selectedTime.hour,
          this.selectedTime.minute,
          this.selectedTime.second
        );
      } else {
        jalaliStr = formatJalaliDate(this.selectedDate.jy, this.selectedDate.jm, this.selectedDate.jd);
      }
      
      // Convert to Gregorian for storage
      const gregorian = jToG(this.selectedDate.jy, this.selectedDate.jm, this.selectedDate.jd);
      let gregorianStr = `${gregorian.gy}-${String(gregorian.gm).padStart(2, '0')}-${String(gregorian.gd).padStart(2, '0')}`;
      
      // Add time for datetime
      if (this.isDateTime) {
        gregorianStr += ` ${String(this.selectedTime.hour).padStart(2, '0')}:${String(this.selectedTime.minute).padStart(2, '0')}:${String(this.selectedTime.second).padStart(2, '0')}`;
      }
      
      console.log(`Converting Jalali ${jalaliStr} to Gregorian ${gregorianStr}`);
      
      // Set the Gregorian value in Frappe's system
      if (this.controlDate && this.controlDate.set_value) {
        console.log(`applySelectedValue: calling controlDate.set_value`);
        this.controlDate.set_value(gregorianStr);
        this.$input.val(jalaliStr);
        console.log(`applySelectedValue: set_value called, isOpen=${this.isOpen}, _isApplyingValue=${this._isApplyingValue}`);
      } else {
        // Fallback: just set the input value
        console.log(`applySelectedValue: setting input value directly`);
        this.$input.val(jalaliStr);
        this.$input.trigger('change');
        console.log(`applySelectedValue: change triggered, isOpen=${this.isOpen}, _isApplyingValue=${this._isApplyingValue}`);
      }
      
      // Clear flag after a delay to allow events to complete
      const self = this;
      setTimeout(function() {
        console.log(`applySelectedValue: clearing _isApplyingValue flag after timeout, isOpen=${self.isOpen}`);
        self._isApplyingValue = false;
      }, 300);
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
    
    selectNow() {
      const now = new Date();
      const today = gToJ(now);
      console.log('Now in Jalali:', today);
      
      // Update current date to today's month/year
      this.currentDate = { ...today };
      
      // Update time to current time
      this.selectedTime = {
        hour: now.getHours(),
        minute: now.getMinutes(),
        second: now.getSeconds()
      };
      
      // Update time picker sliders and labels
      if (this.$calendar && this.$calendar.length) {
        this.$calendar.find('.time-hour').val(this.selectedTime.hour);
        this.$calendar.find('.time-minute').val(this.selectedTime.minute);
        this.$calendar.find('.time-second').val(this.selectedTime.second);
        // Update value labels
        this.$calendar.find('.time-hour-value').text(this.selectedTime.hour);
        this.$calendar.find('.time-minute-value').text(this.selectedTime.minute);
        this.$calendar.find('.time-second-value').text(this.selectedTime.second);
      }
      
      // Set selected date
      this.selectedDate = { ...today };
      
      // Apply the value
      this.applySelectedValue();
      
      // Close calendar after selecting now
      this.close();
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
        if (this.isDateTime) {
          const jalaliDateTime = parseJalaliDateTime(value);
          if (jalaliDateTime) {
            this.selectedDate = {
              jy: jalaliDateTime.jy,
              jm: jalaliDateTime.jm,
              jd: jalaliDateTime.jd
            };
            this.currentDate = { ...this.selectedDate };
            if (jalaliDateTime.hour !== undefined) {
              this.selectedTime = {
                hour: jalaliDateTime.hour || 0,
                minute: jalaliDateTime.minute || 0,
                second: jalaliDateTime.second || 0
              };
              // Update time picker sliders and labels if calendar exists
              if (this.$calendar && this.$calendar.length) {
                this.$calendar.find('.time-hour').val(this.selectedTime.hour);
                this.$calendar.find('.time-minute').val(this.selectedTime.minute);
                this.$calendar.find('.time-second').val(this.selectedTime.second);
                // Update value labels
                this.$calendar.find('.time-hour-value').text(this.selectedTime.hour);
                this.$calendar.find('.time-minute-value').text(this.selectedTime.minute);
                this.$calendar.find('.time-second-value').text(this.selectedTime.second);
              }
            }
          }
        } else {
          const jalali = parseJalaliDate(value);
          if (jalali) {
            this.selectedDate = jalali;
            this.currentDate = { ...jalali };
          }
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

  // Override Frappe's ControlDate and ControlDatetime
  function overrideControlsWhenReady() {
    const hasControls = frappe && frappe.ui && frappe.ui.form && 
                        frappe.ui.form.ControlDate && frappe.ui.form.ControlDatetime;
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
    const BaseControlDatetime = frappe.ui.form.ControlDatetime;

    class JalaliControlDate extends BaseControlDate {
      make_input() {
        console.log(`make_input called for field: ${this.df ? this.df.fieldname : 'unknown'}, jalaliDatepicker exists: ${!!this.jalaliDatepicker}, isOpen: ${this.jalaliDatepicker ? this.jalaliDatepicker.isOpen : 'N/A'}`);
        
        // Check if we should use Jalali datepicker BEFORE calling super
        let useJalali = false;
        let display_calendar = "Gregorian";
        
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
          // Settings not loaded yet - use Gregorian (default Frappe) for now
          // Will be corrected later if Jalali is enabled
          // This prevents creating Jalali datepicker when Gregorian is intended
          useJalali = false;
          display_calendar = "Gregorian";
          
          // Load settings in background and update if needed
          getCalendarSettings().then(settings => {
            // If settings show Jalali, we need to switch to Jalali
            if (settings.enabled && settings.calendar?.display_calendar !== "Gregorian") {
              // Update globals
              if (settings.calendar) {
                EFFECTIVE_CALENDAR = settings.calendar;
              }
              if (settings.firstDay !== undefined) {
                FIRST_DAY = settings.firstDay;
              }
              // Reinitialize with Jalali datepicker
              this.display_calendar = settings.calendar?.display_calendar || "Jalali";
              // Remove any existing datepicker first
              this.removeAirDatepickerInstances();
              if (this.jalaliDatepicker) {
                this.jalaliDatepicker = null;
              }
              // Create Jalali datepicker structure
              this.setupInputWithoutAirDatepicker();
              this.replaceWithJalaliDatepicker();
            }
          });
        }
        
        // Store display_calendar for later use
        this.display_calendar = display_calendar;
        
        // If using Jalali, skip parent make_input and create Jalali datepicker directly
        if (useJalali) {
          // If Jalali datepicker already exists, don't recreate it (preserves open calendar state)
          if (!this.jalaliDatepicker) {
            console.log(`make_input: Creating new Jalali datepicker for field: ${this.df ? this.df.fieldname : 'unknown'}`);
            // Create input structure manually without air-datepicker
            this.setupInputWithoutAirDatepicker();
            // Create Jalali datepicker
            this.replaceWithJalaliDatepicker();
          } else {
            console.log(`make_input: Jalali datepicker already exists for field: ${this.df ? this.df.fieldname : 'unknown'}, skipping recreation`);
            // Datepicker already exists, just ensure setup is correct
            this.setupInputWithoutAirDatepicker();
          }
        } else {
          // Use default Frappe behavior (Gregorian)
          super.make_input();
        }
      }
      
      setupInputWithoutAirDatepicker() {
        // Find or create control-input-wrapper and control-input (like Frappe does)
        let $controlInputWrapper = this.$wrapper.find('.control-input-wrapper');
        let $controlInput = $controlInputWrapper.length ? $controlInputWrapper.find('.control-input') : null;
        
        // Find existing input
        this.$input = this.$wrapper.find('input');
        
        if (!this.$input.length) {
          // Create new input
          this.$input = $(`<input class="form-control" type="text">`);
        }
        
        // Ensure control-input-wrapper exists
        if (!$controlInputWrapper.length) {
          $controlInputWrapper = $('<div class="control-input-wrapper"></div>');
          this.$wrapper.find('.form-group').append($controlInputWrapper);
        }
        
        // Ensure control-input exists
        if (!$controlInput || !$controlInput.length) {
          $controlInput = $('<div class="control-input"></div>');
          $controlInputWrapper.append($controlInput);
        }
        
        // Move input into control-input if it's not already there
        if (!this.$input.closest('.control-input').length) {
          this.$input.detach().appendTo($controlInput);
        }
        
        // Set up basic attributes but prevent air-datepicker initialization
        this.$input.attr('data-fieldtype', this.df.fieldtype || 'Date');
        this.$input.removeClass('datepicker-input hasDatepicker');
        this.$input.removeAttr('data-date-format');
        this.$input.removeAttr('data-alt-input');
        this.$input.removeAttr('data-alt-format');
        this.$input.removeData('datepicker');
      }
      
      replaceWithJalaliDatepicker() {
        // If Jalali datepicker already exists, don't recreate it
        // This prevents calendar from closing when set_value is called
        if (this.jalaliDatepicker) {
          const isCalendarOpen = this.jalaliDatepicker.isOpen;
          console.log(`replaceWithJalaliDatepicker: Jalali datepicker already exists for field: ${this.df ? this.df.fieldname : 'unknown'}, isOpen: ${isCalendarOpen}, skipping recreation`);
          // Always skip recreation if datepicker exists, not just when open
          // This prevents any issues with event handlers being reset
          return;
        }
        
        console.log(`replaceWithJalaliDatepicker: Creating new Jalali datepicker for field: ${this.df ? this.df.fieldname : 'unknown'}`);
        
        // Ensure input exists (should already be created by setupInputWithoutAirDatepicker)
        if (!this.$input || !this.$input.length) {
          this.setupInputWithoutAirDatepicker();
        }
        
        // Make sure no air-datepicker exists (cleanup just in case)
        this.removeAirDatepickerInstances();
        
        // Ensure no air-datepicker classes or attributes
        this.$input.removeAttr('data-date-format');
        this.$input.removeAttr('data-alt-input');
        this.$input.removeAttr('data-alt-format');
        this.$input.removeClass('datepicker-input hasDatepicker');
        this.$input.removeData('datepicker');
        
        // Make input editable for better UX
        this.$input.attr('readonly', false);
        
        // Don't override any styling - let Frappe handle all layout, spacing, and alignment
        
        // Remove any existing air-datepicker instances BEFORE creating Jalali datepicker
        this.removeAirDatepickerInstances();
        
        // Check if this is a datetime field
        const isDateTime = this.df && this.df.fieldtype === "Datetime";
        
        // Mark input as having Jalali datepicker BEFORE creating it
        this.$input.data('hasJalaliDatepicker', true);
        this.$input.attr('data-has-jalali-datepicker', 'true');
        
        // Create Jalali datepicker (with datetime support if needed)
        this.jalaliDatepicker = new JalaliDatepicker(this.$input[0], this, isDateTime);
        
        // Store reference on input for easy access
        this.$input.data('jalaliDatepickerInstance', this.jalaliDatepicker);
        
        // Prevent Frappe from creating air-datepicker on this input
        this.$input.removeClass('datepicker-input hasDatepicker');
        this.$input.off('.datepicker');
        
        // Fix alignment after datepicker creation
        this.fixFieldAlignment();
        
        console.log('Jalali datepicker created for field:', this.df ? this.df.fieldname : 'unknown', 'isDateTime:', isDateTime);
      }
      
      fixFieldAlignment() {
        // Don't override spacing - let Frappe settings control margins and paddings
        // Only ensure essential positioning for datepicker to work correctly
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
        console.log(`set_formatted_input called for field: ${this.df ? this.df.fieldname : 'unknown'}, value: ${value}, jalaliDatepicker exists: ${!!this.jalaliDatepicker}, isOpen: ${this.jalaliDatepicker ? this.jalaliDatepicker.isOpen : 'N/A'}`);
        
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
            // Make sure Jalali datepicker is removed if it exists
            if (this.jalaliDatepicker) {
              this.removeAirDatepickerInstances();
              this.jalaliDatepicker = null;
              // Reinitialize with default Frappe datepicker
              if (this.$input && this.$input.length) {
                // Remove any Jalali-specific attributes
                this.$input.removeAttr('data-has-jalali-datepicker');
                this.$input.removeData('hasJalaliDatepicker');
                this.$input.removeData('jalaliDatepickerInstance');
                // Remove Jalali datepicker DOM element
                this.$input.siblings('.jalali-datepicker').remove();
              }
            }
            console.log('set_formatted_input - Using Gregorian calendar, no conversion');
            return super.set_formatted_input(value);
          }

          // Jalali calendar - convert Gregorian to Jalali for display
          const r = super.set_formatted_input(value);

          // Convert Gregorian to Jalali for display (only when Jalali is enabled)
          if (value) {
            const isDateTimeField = this.df && this.df.fieldtype === "Datetime";
            console.log('set_formatted_input - Input value:', value, 'Display calendar:', display_calendar, 'Is DateTime:', isDateTimeField);
            
            // Parse the date more carefully
            let gregorianDate;
            let timePart = null;
            
            if (typeof value === 'string') {
              // Handle datetime format: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD HH:MM"
              if (value.includes(' ')) {
                const parts = value.split(' ');
                gregorianDate = new Date(parts[0] + 'T' + (parts[1] || '00:00:00'));
                timePart = parts[1] || '00:00:00';
              } else if (value.includes('T')) {
                const parts = value.split('T');
                gregorianDate = new Date(value);
                timePart = parts[1] || '00:00:00';
              } else if (value.includes('-')) {
                gregorianDate = new Date(value + 'T00:00:00');
                timePart = '00:00:00';
              } else {
                gregorianDate = new Date(value);
              }
            } else {
              gregorianDate = new Date(value);
              if (gregorianDate) {
                const hours = gregorianDate.getHours();
                const minutes = gregorianDate.getMinutes();
                const seconds = gregorianDate.getSeconds();
                timePart = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
              }
            }
            
            console.log('set_formatted_input - Parsed date:', gregorianDate, 'Time part:', timePart);
            
            if (!isNaN(gregorianDate.getTime())) {
              const jalali = gToJ(gregorianDate);
              let jalaliStr;
              
              if (isDateTimeField && timePart) {
                jalaliStr = formatJalaliDateTime(jalali.jy, jalali.jm, jalali.jd, 
                  parseInt(timePart.split(':')[0]) || 0,
                  parseInt(timePart.split(':')[1]) || 0,
                  parseInt(timePart.split(':')[2]) || 0
                );
              } else {
                jalaliStr = formatJalaliDate(jalali.jy, jalali.jm, jalali.jd);
              }
              
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

    // Override ControlDate
    frappe.ui.form.ControlDate = JalaliControlDate;
    console.log("ControlDate patched for Jalali");
    
    // Override ControlDatetime - it should inherit from JalaliControlDate
    // But we need to make sure datetime-specific methods are preserved
    class JalaliControlDatetime extends JalaliControlDate {
      // ControlDatetime extends ControlDate, so JalaliControlDatetime should extend JalaliControlDate
      // This ensures datetime fields also use Jalali datepicker
      
      // Override make_input to ensure datetime fields are treated correctly
      make_input() {
        // Call parent (JalaliControlDate.make_input) which will handle Jalali datepicker
        super.make_input();
        
        // For datetime fields, if we're using Gregorian (no Jalali datepicker), 
        // we need to call set_date_options to configure the time picker
        if (!this.jalaliDatepicker && BaseControlDatetime.prototype.set_date_options) {
          // Call the base ControlDatetime's set_date_options to configure time picker
          BaseControlDatetime.prototype.set_date_options.call(this);
        }
      }
      
      // Preserve ControlDatetime's set_date_options to ensure timepicker is configured
      set_date_options() {
        // Check if we should use Jalali (if Jalali datepicker exists, we handle time ourselves)
        if (this.jalaliDatepicker) {
        // Don't call super.set_date_options() as we handle datepicker ourselves
          return;
        }
        // For Gregorian, call the base ControlDatetime's set_date_options to configure time picker
        // This ensures the default Frappe time picker is properly configured
        return BaseControlDatetime.prototype.set_date_options.call(this);
      }
      
      // Preserve other ControlDatetime methods that might be needed
      get_now_date() {
        return frappe.datetime.now_datetime(true);
      }
      
      set_formatted_input(value) {
        // For datetime fields, we still want to use our Jalali formatting
        // Call parent's set_formatted_input which handles Jalali conversion
        return super.set_formatted_input(value);
      }
    }
    
    frappe.ui.form.ControlDatetime = JalaliControlDatetime;
    console.log("ControlDatetime patched for Jalali");
  }

  // Function to remove all existing air-datepicker instances from the page
  function removeAllAirDatepickerInstances() {
    // Only target inputs that don't have jalali-datepicker
    const $airDatepickerInputs = $('input.datepicker-input, input.hasDatepicker').filter(function() {
      // Skip inputs that already have jalali-datepicker instance
      const $input = $(this);
      // Check multiple ways to identify Jalali datepicker
      const hasJalaliAttr = $input.attr('data-has-jalali-datepicker') === 'true';
      const hasJalaliData = $input.data('hasJalaliDatepicker') === true;
      const jalaliInstance = $input.siblings('.jalali-datepicker').data('jalaliDatepickerInstance');
      const jalaliDataInstance = $input.data('jalaliDatepickerInstance');
      
      // Skip if any Jalali datepicker indicator is present
      return !hasJalaliAttr && !hasJalaliData && !jalaliInstance && !jalaliDataInstance;
    });
    
    // Only proceed if there are actual air-datepicker instances to remove
    const hasAirDatepicker = $('.air-datepicker').length > 0 || $airDatepickerInputs.length > 0;
    
    if (!hasAirDatepicker) {
      // No air-datepicker instances found, skip removal to avoid unnecessary processing
      return;
    }
    
    // Remove all air-datepicker calendars (but not jalali-datepicker)
    $('.air-datepicker').not('.jalali-datepicker').remove();
    
    // Remove air-datepicker classes and attributes from filtered inputs only
    $airDatepickerInputs.each(function() {
      const $input = $(this);
      // Double check this input doesn't have jalali-datepicker
      const hasJalaliAttr = $input.attr('data-has-jalali-datepicker') === 'true';
      const hasJalaliData = $input.data('hasJalaliDatepicker') === true;
      const jalaliInstance = $input.siblings('.jalali-datepicker').data('jalaliDatepickerInstance');
      const jalaliDataInstance = $input.data('jalaliDatepickerInstance');
      
      if (hasJalaliAttr || hasJalaliData || jalaliInstance || jalaliDataInstance) {
        return; // Skip this input
      }
      
      $input.removeClass('datepicker-input hasDatepicker');
      $input.removeAttr('data-date-format');
      $input.removeAttr('data-alt-input');
      $input.removeAttr('data-alt-format');
      $input.removeData('datepicker');
      
      // Remove event listeners
      $input.off('.datepicker');
    });
    
    // Remove any datepicker icons or buttons (but not jalali datepicker buttons)
    $('.datepicker-icon, .datepicker-btn').not('.jalali-datepicker .today-btn, .jalali-datepicker .now-btn').remove();
    
    // Remove any air-datepicker instances from global scope
    if (window.Datepicker && window.Datepicker.instances) {
      try {
        // Try to destroy all instances that are not our Jalali datepickers
        Object.keys(window.Datepicker.instances).forEach(key => {
          try {
            const instance = window.Datepicker.instances[key];
            // Only destroy if it's a real air-datepicker instance
            // Check if the input has jalali-datepicker sibling
            if (instance && instance.el) {
              const $el = $(instance.el);
              const hasJalaliSibling = $el.siblings('.jalali-datepicker').length > 0;
              if (!hasJalaliSibling && !$el.data('jalaliDatepickerInstance')) {
                instance.destroy();
              }
            }
          } catch(e) {
            // Silently ignore errors for individual instances
          }
        });
      } catch(e) {
        // Silently ignore errors accessing instances
      }
    }
  }
  
  // Remove existing air-datepicker instances immediately
  removeAllAirDatepickerInstances();
  
  // Also remove them periodically to catch any dynamically created ones
  // Use longer interval and only remove if needed
  setInterval(function() {
    // Only run cleanup if there are actual air-datepicker instances
    if ($('.air-datepicker').not('.jalali-datepicker').length > 0 || 
        $('input.datepicker-input, input.hasDatepicker').filter(function() {
          const $input = $(this);
          // Check all ways to identify Jalali datepicker
          const hasJalaliAttr = $input.attr('data-has-jalali-datepicker') === 'true';
          const hasJalaliData = $input.data('hasJalaliDatepicker') === true;
          const jalaliSiblingInstance = $input.siblings('.jalali-datepicker').data('jalaliDatepickerInstance');
          const jalaliDataInstance = $input.data('jalaliDatepickerInstance');
          
          // Return true only if NO Jalali datepicker indicators are present
          return !hasJalaliAttr && !hasJalaliData && !jalaliSiblingInstance && !jalaliDataInstance;
        }).length > 0) {
      removeAllAirDatepickerInstances();
    }
  }, 2000); // Changed from 1000ms to 2000ms to be less aggressive

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