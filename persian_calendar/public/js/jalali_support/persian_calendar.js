(async function() {
  frappe.provide("frappe.ui.form");

  console.log("jalali_support script loaded");

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
    console.log("Jalali calendar is disabled, skipping datepicker overrides");
    return; // Exit the entire script if disabled
  }

  // If Jalali is enabled, proceed with fetching week bounds and overriding controls
  let FIRST_DAY = 6;
  try {
    const r = await frappe.call({ method: "persian_calendar.jalali_support.api.get_week_bounds" });
    if (r && r.message && r.message.week_start != null) {
      FIRST_DAY = r.message.week_start;
    }
    console.log("Week start day:", FIRST_DAY);
  } catch(e) {
    console.log("Error fetching week bounds:", e);
  }

function gToJ(gDate) {
  return toJalali(gDate.getFullYear(), gDate.getMonth() + 1, gDate.getDate());
}

function jToG(jy, jm, jd) {
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

function overrideControlsWhenReady() {
  const hasControls = frappe && frappe.ui && frappe.ui.form && frappe.ui.form.ControlDate && frappe.ui.form.ControlDatetime;
  if (!hasControls) {
    setTimeout(overrideControlsWhenReady, 50);
    return;
  }

  const BaseControlDate = frappe.ui.form.ControlDate;
  const BaseControlDatetime = frappe.ui.form.ControlDatetime;

  // Check if already patched
  if (BaseControlDate.__jalali_patched) {
    return;
  }

  class JalaliControlDate extends BaseControlDate {
    make_input() {
      // Create input element manually to avoid flatpickr initialization
      this.$input = this.$wrapper.find('input');
      if (!this.$input.length) {
        this.$input = $(`<input class="form-control" type="text">`);
        this.$wrapper.append(this.$input);
      }
      
      // Remove any existing flatpickr attributes and classes
      this.$input.removeAttr('data-input');
      this.$input.removeClass('flatpickr-input');
      this.$input.removeAttr('readonly');
      
      // Make input editable for better UX
      this.$input.attr('readonly', false);
      
      // Create custom Jalali datepicker
      this.createJalaliDatepicker();
    }

    createJalaliDatepicker() {
      const me = this;
      const $input = this.$input;
      
      // Remove existing calendar if any
      $input.siblings('.jalali-calendar').remove();
      
      // Create calendar container
      const $calendar = $(`
        <div class="jalali-calendar" style="display: none; position: absolute; background: white; border: 1px solid #ccc; border-radius: 4px; padding: 10px; z-index: 1000; box-shadow: 0 2px 10px rgba(0,0,0,0.1); min-width: 280px;">
          <div class="calendar-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <button type="button" class="prev-year" style="background: none; border: none; cursor: pointer; padding: 5px; font-size: 16px;">‹‹</button>
            <button type="button" class="prev-month" style="background: none; border: none; cursor: pointer; padding: 5px; font-size: 16px;">‹</button>
            <span class="current-month-year" style="font-weight: bold; cursor: pointer; padding: 5px; border-radius: 3px; min-width: 120px; text-align: center;" title="کلیک برای تغییر سال و ماه"></span>
            <button type="button" class="next-month" style="background: none; border: none; cursor: pointer; padding: 5px; font-size: 16px;">›</button>
            <button type="button" class="next-year" style="background: none; border: none; cursor: pointer; padding: 5px; font-size: 16px;">››</button>
          </div>
          <div class="calendar-weekdays" style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; margin-bottom: 5px;">
            <!-- Weekdays will be populated dynamically based on FIRST_DAY -->
          </div>
          <div class="calendar-days" style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; margin-bottom: 10px;"></div>
          <div class="calendar-footer" style="text-align: center; border-top: 1px solid #eee; padding-top: 8px;">
            <button type="button" class="today-btn" style="background: #007bff; color: white; border: none; padding: 6px 12px; border-radius: 3px; cursor: pointer; font-size: 12px;">امروز</button>
          </div>
        </div>
      `);
      
      // Insert calendar after input
      $input.after($calendar);
      
      // Current Jalali date - get current date
      const now = new Date();
      let currentJalali = gToJ(now);
      
      // Store calendar reference for easy access
      me.$jalaliCalendar = $calendar;
      
      // Update calendar display
      const updateCalendar = () => {
        const monthNames = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 
                          'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
        
        $calendar.find('.current-month-year').text(`${monthNames[currentJalali.jm - 1]} ${currentJalali.jy}`);
        
        // Update weekdays based on FIRST_DAY
        const weekdayNames = ['ی', 'د', 'س', 'چ', 'پ', 'ج', 'ش']; // Sunday=0 to Saturday=6
        const $weekdaysContainer = $calendar.find('.calendar-weekdays');
        $weekdaysContainer.empty();
        
        // Start from FIRST_DAY and cycle through 7 days
        for (let i = 0; i < 7; i++) {
          const dayIndex = (FIRST_DAY + i) % 7;
          const $weekday = $(`<div style="text-align: center; font-weight: bold; padding: 5px; font-size: 12px;">${weekdayNames[dayIndex]}</div>`);
          $weekdaysContainer.append($weekday);
        }
        
        // Generate days for current month
        const daysInMonth = currentJalali.jm <= 6 ? 31 : (currentJalali.jm <= 11 ? 30 : (currentJalali.jy % 4 === 3 ? 30 : 29));
        const $daysContainer = $calendar.find('.calendar-days');
        $daysContainer.empty();
        
        for (let day = 1; day <= daysInMonth; day++) {
          const $day = $(`<div class="calendar-day" data-day="${day}" style="text-align: center; padding: 8px; cursor: pointer; border-radius: 3px; transition: all 0.2s;">${day}</div>`);
          
          // Add hover effect
          $day.on('mouseenter', function() {
            if (!$(this).hasClass('selected')) {
              $(this).css('background-color', '#f8f9fa');
            }
          }).on('mouseleave', function() {
            if (!$(this).hasClass('selected')) {
              $(this).css('background-color', '');
            }
          });
          
          // Highlight current day if it matches input value
          const inputValue = $input.val();
          if (inputValue) {
            const jalali = parseJalaliDate(inputValue);
            if (jalali && jalali.jy === currentJalali.jy && jalali.jm === currentJalali.jm && jalali.jd === day) {
              $day.addClass('selected').css('background-color', '#007bff').css('color', 'white');
            }
          }
          
          // Day click handler
          $day.on('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const selectedDay = parseInt($(this).data('day'));
            console.log('Selected day:', selectedDay, 'Current Jalali before:', currentJalali);
            
            // Check if this day is already selected (has blue background)
            const isAlreadySelected = $(this).hasClass('selected') && $(this).css('background-color') === 'rgb(0, 123, 255)';
            
            if (isAlreadySelected) {
              // If clicking on already selected day, clear the selection
              console.log('Clearing selection for day:', selectedDay);
              
              // Remove highlight from all days
              $calendar.find('.calendar-day').removeClass('selected').css('background-color', '').css('color', '');
              
              // Clear input value
              $input.val('');
              
              // Close calendar immediately
              console.log('Hiding calendar...');
              $calendar.hide();
              
              // Set empty value using Frappe's method
              setTimeout(() => {
                console.log('Calling set_value with empty string...');
                me.set_value('');
              }, 10);
              
              return; // Exit early
            }
            
            // Create a fresh Jalali date object with the selected day
            const newJalali = {
              jy: currentJalali.jy,
              jm: currentJalali.jm,
              jd: selectedDay
            };
            console.log('New Jalali:', newJalali);
            
            const jalaliStr = formatJalaliDate(newJalali.jy, newJalali.jm, newJalali.jd);
            console.log('Setting Jalali string:', jalaliStr);
            
            // Convert to Gregorian for storage
            const gregorian = jToG(newJalali.jy, newJalali.jm, newJalali.jd);
            const gregorianStr = `${gregorian.gy}-${String(gregorian.gm).padStart(2, '0')}-${String(gregorian.gd).padStart(2, '0')}`;
            console.log('Setting Gregorian string:', gregorianStr);
            
            // Update current Jalali date first
            currentJalali.jd = selectedDay;
            
            // Update calendar to highlight selected day immediately
            $calendar.find('.calendar-day').removeClass('selected').css('background-color', '').css('color', '');
            $(this).addClass('selected').css('background-color', '#007bff').css('color', 'white');
            
            // Set input value directly first
            $input.val(jalaliStr);
            
            // Close calendar immediately
            console.log('Hiding calendar...');
            $calendar.hide();
            
            // Set the value using Frappe's method after hiding calendar
            setTimeout(() => {
              console.log('Calling set_value...');
              me.set_value(gregorianStr);
            }, 10);
          });
          
          $daysContainer.append($day);
        }
      };
      
      // Navigation handlers
      $calendar.find('.prev-year').on('click', () => {
        currentJalali.jy--;
        updateCalendar();
      });
      
      $calendar.find('.next-year').on('click', () => {
        currentJalali.jy++;
        updateCalendar();
      });
      
      $calendar.find('.prev-month').on('click', () => {
        if (currentJalali.jm === 1) {
          currentJalali.jm = 12;
          currentJalali.jy--;
        } else {
          currentJalali.jm--;
        }
        updateCalendar();
      });
      
      $calendar.find('.next-month').on('click', () => {
        if (currentJalali.jm === 12) {
          currentJalali.jm = 1;
          currentJalali.jy++;
        } else {
          currentJalali.jm++;
        }
        updateCalendar();
      });
      
          // Click on month/year to show quick selection
          $calendar.find('.current-month-year').on('click', () => {
            const newYear = prompt('سال جدید را وارد کنید:', currentJalali.jy);
            if (newYear && !isNaN(newYear) && newYear > 1300 && newYear < 1500) {
              currentJalali.jy = parseInt(newYear);
              updateCalendar();
            }
          });

          // Today button handler
          $calendar.find('.today-btn').on('click', () => {
            const today = new Date();
            const todayJalali = gToJ(today);
            
            // Set to today's date
            currentJalali = { jy: todayJalali.jy, jm: todayJalali.jm, jd: todayJalali.jd };
            
            const jalaliStr = formatJalaliDate(todayJalali.jy, todayJalali.jm, todayJalali.jd);
            $input.val(jalaliStr);
            
            // Convert to Gregorian for storage
            const gregorian = jToG(todayJalali.jy, todayJalali.jm, todayJalali.jd);
            const gregorianStr = `${gregorian.gy}-${String(gregorian.gm).padStart(2, '0')}-${String(gregorian.gd).padStart(2, '0')}`;
            
            // Set the value using Frappe's method
            me.set_value(gregorianStr);
            
            // Force update the input display
            setTimeout(() => {
              if ($input.val() !== jalaliStr) {
                $input.val(jalaliStr);
              }
            }, 100);
            
            // Update calendar and close
            updateCalendar();
            $calendar.hide();
          });
      
      // Show calendar on input click
      $input.on('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        
        // Set current month to input value if exists
        const inputValue = $input.val();
        if (inputValue) {
          const jalali = parseJalaliDate(inputValue);
          if (jalali) {
            currentJalali = { jy: jalali.jy, jm: jalali.jm, jd: jalali.jd };
          }
        }
        
        updateCalendar();
        
        // Position calendar
        const inputRect = $input[0].getBoundingClientRect();
        $calendar.css({
          position: 'fixed',
          top: inputRect.bottom + window.scrollY + 5,
          left: inputRect.left + window.scrollX,
          display: 'block'
        });
      });
      
      // Hide calendar when clicking outside
      $(document).on('click', (e) => {
        if (!$(e.target).closest('.jalali-calendar, .form-control').length) {
          $calendar.hide();
        }
      });
      
      // Initialize calendar
      updateCalendar();
    }

        set_formatted_input(value) {
          try {
            const r = super.set_formatted_input(value);

            // Convert Gregorian to Jalali for display
            if (value) {
              const gregorianDate = new Date(value + 'T00:00:00Z');
              const jalali = gToJ(gregorianDate);
              const jalaliStr = formatJalaliDate(jalali.jy, jalali.jm, jalali.jd);
              console.log('set_formatted_input - Gregorian:', value, 'Jalali:', jalaliStr);
              this.$input.val(jalaliStr);
              
              // Only update calendar highlight if calendar is closed (to prevent interference)
              const $calendar = this.$input.siblings('.jalali-calendar');
              if ($calendar.length && !$calendar.is(':visible')) {
                // Update current Jalali date for next time calendar opens
                // This ensures the calendar shows the correct month/year when reopened
                const currentJalali = { jy: jalali.jy, jm: jalali.jm, jd: jalali.jd };
              }
            }

            return r;
          } catch(e) {
            console.log('set_formatted_input error:', e);
            return super.set_formatted_input(value);
          }
        }
  }

  class JalaliControlDatetime extends BaseControlDatetime {
    make_input() {
      // Create input element without calling super.make_input()
      this.$input = this.$wrapper.find('input');
      if (!this.$input.length) {
        this.$input = $(`<input class="form-control" type="text" readonly>`);
        this.$wrapper.append(this.$input);
      }
      
      // Make input editable for better UX
      this.$input.attr('readonly', false);
      
      // Create custom Jalali datetime picker
      this.createJalaliDatetimePicker();
    }

    createJalaliDatetimePicker() {
      const me = this;
      const $input = this.$input;
      
      // Create datetime picker container
      const $picker = $(`
        <div class="jalali-datetime-picker" style="display: none; position: absolute; background: white; border: 1px solid #ccc; border-radius: 4px; padding: 10px; z-index: 1000; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
          <div class="calendar-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <button type="button" class="prev-month" style="background: none; border: none; cursor: pointer;">‹</button>
            <span class="current-month-year" style="font-weight: bold;"></span>
            <button type="button" class="next-month" style="background: none; border: none; cursor: pointer;">›</button>
          </div>
          <div class="calendar-weekdays" style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; margin-bottom: 5px;">
            <div style="text-align: center; font-weight: bold; padding: 5px;">ش</div>
            <div style="text-align: center; font-weight: bold; padding: 5px;">ی</div>
            <div style="text-align: center; font-weight: bold; padding: 5px;">د</div>
            <div style="text-align: center; font-weight: bold; padding: 5px;">س</div>
            <div style="text-align: center; font-weight: bold; padding: 5px;">چ</div>
            <div style="text-align: center; font-weight: bold; padding: 5px;">پ</div>
            <div style="text-align: center; font-weight: bold; padding: 5px;">ج</div>
          </div>
          <div class="calendar-days" style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; margin-bottom: 10px;"></div>
          <div class="time-picker" style="display: flex; gap: 10px; align-items: center; justify-content: center;">
            <input type="number" class="hour-input" min="0" max="23" placeholder="ساعت" style="width: 60px; padding: 5px; border: 1px solid #ccc; border-radius: 3px;">
            <span>:</span>
            <input type="number" class="minute-input" min="0" max="59" placeholder="دقیقه" style="width: 60px; padding: 5px; border: 1px solid #ccc; border-radius: 3px;">
          </div>
          <div class="picker-actions" style="display: flex; gap: 10px; justify-content: center; margin-top: 10px;">
            <button type="button" class="btn-ok" style="background: #007bff; color: white; border: none; padding: 5px 15px; border-radius: 3px; cursor: pointer;">تأیید</button>
            <button type="button" class="btn-cancel" style="background: #6c757d; color: white; border: none; padding: 5px 15px; border-radius: 3px; cursor: pointer;">لغو</button>
          </div>
        </div>
      `);
      
      // Insert picker after input
      $input.after($picker);
      
      // Current Jalali date - get current date
      const now = new Date();
      let currentJalali = gToJ(now);
      let selectedTime = { hour: now.getHours(), minute: now.getMinutes() };
      
      // Update calendar display
      const updateCalendar = () => {
        const monthNames = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 
                          'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
        
        $picker.find('.current-month-year').text(`${monthNames[currentJalali.jm - 1]} ${currentJalali.jy}`);
        
        // Generate days for current month
        const daysInMonth = currentJalali.jm <= 6 ? 31 : (currentJalali.jm <= 11 ? 30 : (currentJalali.jy % 4 === 3 ? 30 : 29));
        const $daysContainer = $picker.find('.calendar-days');
        $daysContainer.empty();
        
        for (let day = 1; day <= daysInMonth; day++) {
          const $day = $(`<div class="calendar-day" data-day="${day}" style="text-align: center; padding: 8px; cursor: pointer; border-radius: 3px;">${day}</div>`);
          
          // Highlight current day if it matches input value
          const inputValue = $input.val();
          if (inputValue) {
            const parts = inputValue.split(' ');
            if (parts.length === 2) {
              const jalali = parseJalaliDate(parts[0]);
              if (jalali && jalali.jy === currentJalali.jy && jalali.jm === currentJalali.jm && jalali.jd === day) {
                $day.css('background-color', '#007bff').css('color', 'white');
              }
            }
          }
          
          // Day click handler
          $day.on('click', function() {
            const selectedDay = parseInt($(this).data('day'));
            currentJalali.jd = selectedDay;
            
            // Update time inputs
            $picker.find('.hour-input').val(selectedTime.hour);
            $picker.find('.minute-input').val(selectedTime.minute);
            
            // Highlight selected day
            $picker.find('.calendar-day').removeClass('selected');
            $(this).addClass('selected');
          });
          
          $daysContainer.append($day);
        }
      };
      
      // Navigation handlers
      $picker.find('.prev-month').on('click', () => {
        if (currentJalali.jm === 1) {
          currentJalali.jm = 12;
          currentJalali.jy--;
        } else {
          currentJalali.jm--;
        }
        updateCalendar();
      });
      
      $picker.find('.next-month').on('click', () => {
        if (currentJalali.jm === 12) {
          currentJalali.jm = 1;
          currentJalali.jy++;
        } else {
          currentJalali.jm++;
        }
        updateCalendar();
      });
      
      // OK button handler
      $picker.find('.btn-ok').on('click', () => {
        const hour = parseInt($picker.find('.hour-input').val()) || 0;
        const minute = parseInt($picker.find('.minute-input').val()) || 0;
        
        const jalaliStr = `${formatJalaliDate(currentJalali.jy, currentJalali.jm, currentJalali.jd)} ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
        $input.val(jalaliStr);
        
        // Convert to Gregorian for storage
        const gregorian = jToG(currentJalali.jy, currentJalali.jm, currentJalali.jd);
        const gregorianStr = `${gregorian.gy}-${String(gregorian.gm).padStart(2, '0')}-${String(gregorian.gd).padStart(2, '0')} ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00`;
        me.set_value(gregorianStr);
        
        $picker.hide();
      });
      
      // Cancel button handler
      $picker.find('.btn-cancel').on('click', () => {
        $picker.hide();
      });
      
      // Show picker on input click
      $input.on('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        
        // Set current month to input value if exists
        const inputValue = $input.val();
        if (inputValue) {
          const parts = inputValue.split(' ');
          if (parts.length === 2) {
            const jalali = parseJalaliDate(parts[0]);
            if (jalali) {
              currentJalali = { jy: jalali.jy, jm: jalali.jm, jd: jalali.jd };
            }
            
            const timeParts = parts[1].split(':');
            if (timeParts.length === 2) {
              selectedTime.hour = parseInt(timeParts[0]) || 0;
              selectedTime.minute = parseInt(timeParts[1]) || 0;
            }
          }
        }
        
        updateCalendar();
        
        // Position picker
        const inputRect = $input[0].getBoundingClientRect();
        $picker.css({
          position: 'fixed',
          top: inputRect.bottom + window.scrollY + 5,
          left: inputRect.left + window.scrollX,
          display: 'block'
        });
      });
      
      // Hide picker when clicking outside
      $(document).on('click', (e) => {
        if (!$(e.target).closest('.jalali-datetime-picker, .form-control').length) {
          $picker.hide();
        }
      });
      
      // Initialize picker
      updateCalendar();
    }

    set_formatted_input(value) {
      try {
        const r = super.set_formatted_input(value);
        
        // Convert Gregorian to Jalali for display
        if (value) {
          const gregorianDate = new Date(value + 'Z');
          const jalali = gToJ(gregorianDate);
          const hh = String(gregorianDate.getHours()).padStart(2, "0");
          const mm = String(gregorianDate.getMinutes()).padStart(2, "0");
          const jalaliStr = `${formatJalaliDate(jalali.jy, jalali.jm, jalali.jd)} ${hh}:${mm}`;
          this.$input.val(jalaliStr);
        }
        
        return r;
      } catch(e) {
        return super.set_formatted_input(value);
      }
    }
  }

  frappe.ui.form.ControlDate = JalaliControlDate;
  frappe.ui.form.ControlDatetime = JalaliControlDatetime;
  console.log("ControlDate & ControlDatetime patched for Jalali");
  
  // Call overrideControlsWhenReady only if jalaliEnabled is true
  overrideControlsWhenReady();
}

})(); // End of async IIFE


