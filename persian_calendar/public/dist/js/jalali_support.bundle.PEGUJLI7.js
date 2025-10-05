(() => {
  // ../persian_calendar/persian_calendar/public/js/jalali_support/jalaali.js
  (function() {
    const fmt = new Intl.DateTimeFormat("en-u-ca-persian", { year: "numeric", month: "2-digit", day: "2-digit" });
    function toJalaliPartsFromGregorianDate(gDate) {
      const parts = fmt.formatToParts(gDate);
      const map = Object.fromEntries(parts.map((p) => [p.type, p.value]));
      const jy = parseInt(map.year, 10);
      const jm = parseInt(map.month, 10);
      const jd = parseInt(map.day, 10);
      return { jy, jm, jd };
    }
    function toJalali2(gy, gm, gd) {
      return toJalaliPartsFromGregorianDate(new Date(Date.UTC(gy, gm - 1, gd)));
    }
    function toGregorian2(jy, jm, jd) {
      const startYear = 2e3;
      const endYear = 2030;
      for (let year = startYear; year <= endYear; year++) {
        for (let month = 1; month <= 12; month++) {
          for (let day = 1; day <= 31; day++) {
            try {
              const testDate = new Date(year, month - 1, day);
              const testJalali = toJalaliPartsFromGregorianDate(testDate);
              if (testJalali.jy === jy && testJalali.jm === jm && testJalali.jd === jd) {
                return {
                  gy: year,
                  gm: month,
                  gd: day
                };
              }
            } catch (e) {
              continue;
            }
          }
        }
      }
      const approximateDate = new Date(2e3, 6, 1);
      const approximateJalali = toJalaliPartsFromGregorianDate(approximateDate);
      const yearDiff = jy - approximateJalali.jy;
      const monthDiff = jm - approximateJalali.jm;
      const dayDiff = jd - approximateJalali.jd;
      const totalDays = yearDiff * 365 + monthDiff * 30 + dayDiff;
      const resultDate = new Date(approximateDate.getTime() + totalDays * 24 * 60 * 60 * 1e3);
      return {
        gy: resultDate.getFullYear(),
        gm: resultDate.getMonth() + 1,
        gd: resultDate.getDate()
      };
    }
    window.toJalali = toJalali2;
    window.toGregorian = toGregorian2;
    window.toJalaliPartsFromGregorianDate = toJalaliPartsFromGregorianDate;
  })();

  // ../persian_calendar/persian_calendar/public/js/jalali_support/persian_calendar.js
  (async function() {
    frappe.provide("frappe.ui.form");
    console.log("jalali_support script loaded");
    let jalaliEnabled = false;
    try {
      const result = await frappe.call({ method: "persian_calendar.jalali_support.api.is_jalali_enabled" });
      jalaliEnabled = result && result.message;
      console.log("Jalali calendar enabled:", jalaliEnabled);
    } catch (e) {
      console.log("Error checking Jalali settings:", e);
      jalaliEnabled = false;
    }
    if (!jalaliEnabled) {
      console.log("Jalali calendar is disabled, skipping datepicker overrides");
      return;
    }
    let FIRST_DAY = 6;
    try {
      const r = await frappe.call({ method: "persian_calendar.jalali_support.api.get_week_bounds" });
      if (r && r.message && r.message.week_start != null) {
        FIRST_DAY = r.message.week_start;
      }
      console.log("Week start day:", FIRST_DAY);
    } catch (e) {
      console.log("Error fetching week bounds:", e);
    }
    function gToJ(gDate) {
      return toJalali(gDate.getFullYear(), gDate.getMonth() + 1, gDate.getDate());
    }
    function jToG(jy, jm, jd) {
      return toGregorian(jy, jm, jd);
    }
    function formatJalaliDate(jy, jm, jd) {
      return `${jy}-${String(jm).padStart(2, "0")}-${String(jd).padStart(2, "0")}`;
    }
    function parseJalaliDate(dateStr) {
      const parts = dateStr.split("-").map(Number);
      if (parts.length !== 3)
        return null;
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
      if (BaseControlDate.__jalali_patched) {
        return;
      }
      class JalaliControlDate extends BaseControlDate {
        make_input() {
          this.$input = this.$wrapper.find("input");
          if (!this.$input.length) {
            this.$input = $(`<input class="form-control" type="text">`);
            this.$wrapper.append(this.$input);
          }
          this.$input.removeAttr("data-input");
          this.$input.removeClass("flatpickr-input");
          this.$input.removeAttr("readonly");
          this.$input.attr("readonly", false);
          this.createJalaliDatepicker();
        }
        createJalaliDatepicker() {
          const me = this;
          const $input = this.$input;
          $input.siblings(".jalali-calendar").remove();
          const $calendar = $(`
        <div class="jalali-calendar" style="display: none; position: absolute; background: white; border: 1px solid #ccc; border-radius: 4px; padding: 10px; z-index: 1000; box-shadow: 0 2px 10px rgba(0,0,0,0.1); min-width: 280px;">
          <div class="calendar-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <button type="button" class="prev-year" style="background: none; border: none; cursor: pointer; padding: 5px; font-size: 16px;">\u2039\u2039</button>
            <button type="button" class="prev-month" style="background: none; border: none; cursor: pointer; padding: 5px; font-size: 16px;">\u2039</button>
            <span class="current-month-year" style="font-weight: bold; cursor: pointer; padding: 5px; border-radius: 3px; min-width: 120px; text-align: center;" title="\u06A9\u0644\u06CC\u06A9 \u0628\u0631\u0627\u06CC \u062A\u063A\u06CC\u06CC\u0631 \u0633\u0627\u0644 \u0648 \u0645\u0627\u0647"></span>
            <button type="button" class="next-month" style="background: none; border: none; cursor: pointer; padding: 5px; font-size: 16px;">\u203A</button>
            <button type="button" class="next-year" style="background: none; border: none; cursor: pointer; padding: 5px; font-size: 16px;">\u203A\u203A</button>
          </div>
          <div class="calendar-weekdays" style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; margin-bottom: 5px;">
            <!-- Weekdays will be populated dynamically based on FIRST_DAY -->
          </div>
          <div class="calendar-days" style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; margin-bottom: 10px;"></div>
          <div class="calendar-footer" style="text-align: center; border-top: 1px solid #eee; padding-top: 8px;">
            <button type="button" class="today-btn" style="background: #007bff; color: white; border: none; padding: 6px 12px; border-radius: 3px; cursor: pointer; font-size: 12px;">\u0627\u0645\u0631\u0648\u0632</button>
          </div>
        </div>
      `);
          $input.after($calendar);
          const now = new Date();
          let currentJalali = gToJ(now);
          me.$jalaliCalendar = $calendar;
          const updateCalendar = () => {
            const monthNames = [
              "\u0641\u0631\u0648\u0631\u062F\u06CC\u0646",
              "\u0627\u0631\u062F\u06CC\u0628\u0647\u0634\u062A",
              "\u062E\u0631\u062F\u0627\u062F",
              "\u062A\u06CC\u0631",
              "\u0645\u0631\u062F\u0627\u062F",
              "\u0634\u0647\u0631\u06CC\u0648\u0631",
              "\u0645\u0647\u0631",
              "\u0622\u0628\u0627\u0646",
              "\u0622\u0630\u0631",
              "\u062F\u06CC",
              "\u0628\u0647\u0645\u0646",
              "\u0627\u0633\u0641\u0646\u062F"
            ];
            $calendar.find(".current-month-year").text(`${monthNames[currentJalali.jm - 1]} ${currentJalali.jy}`);
            const weekdayNames = ["\u06CC", "\u062F", "\u0633", "\u0686", "\u067E", "\u062C", "\u0634"];
            const $weekdaysContainer = $calendar.find(".calendar-weekdays");
            $weekdaysContainer.empty();
            for (let i = 0; i < 7; i++) {
              const dayIndex = (FIRST_DAY + i) % 7;
              const $weekday = $(`<div style="text-align: center; font-weight: bold; padding: 5px; font-size: 12px;">${weekdayNames[dayIndex]}</div>`);
              $weekdaysContainer.append($weekday);
            }
            const daysInMonth = currentJalali.jm <= 6 ? 31 : currentJalali.jm <= 11 ? 30 : currentJalali.jy % 4 === 3 ? 30 : 29;
            const $daysContainer = $calendar.find(".calendar-days");
            $daysContainer.empty();
            for (let day = 1; day <= daysInMonth; day++) {
              const $day = $(`<div class="calendar-day" data-day="${day}" style="text-align: center; padding: 8px; cursor: pointer; border-radius: 3px; transition: all 0.2s;">${day}</div>`);
              $day.on("mouseenter", function() {
                if (!$(this).hasClass("selected")) {
                  $(this).css("background-color", "#f8f9fa");
                }
              }).on("mouseleave", function() {
                if (!$(this).hasClass("selected")) {
                  $(this).css("background-color", "");
                }
              });
              const inputValue = $input.val();
              if (inputValue) {
                const jalali = parseJalaliDate(inputValue);
                if (jalali && jalali.jy === currentJalali.jy && jalali.jm === currentJalali.jm && jalali.jd === day) {
                  $day.addClass("selected").css("background-color", "#007bff").css("color", "white");
                }
              }
              $day.on("click", function(e) {
                e.preventDefault();
                e.stopPropagation();
                const selectedDay = parseInt($(this).data("day"));
                console.log("Selected day:", selectedDay, "Current Jalali before:", currentJalali);
                const isAlreadySelected = $(this).hasClass("selected") && $(this).css("background-color") === "rgb(0, 123, 255)";
                if (isAlreadySelected) {
                  console.log("Clearing selection for day:", selectedDay);
                  $calendar.find(".calendar-day").removeClass("selected").css("background-color", "").css("color", "");
                  $input.val("");
                  console.log("Hiding calendar...");
                  $calendar.hide();
                  setTimeout(() => {
                    console.log("Calling set_value with empty string...");
                    me.set_value("");
                  }, 10);
                  return;
                }
                const newJalali = {
                  jy: currentJalali.jy,
                  jm: currentJalali.jm,
                  jd: selectedDay
                };
                console.log("New Jalali:", newJalali);
                const jalaliStr = formatJalaliDate(newJalali.jy, newJalali.jm, newJalali.jd);
                console.log("Setting Jalali string:", jalaliStr);
                const gregorian = jToG(newJalali.jy, newJalali.jm, newJalali.jd);
                const gregorianStr = `${gregorian.gy}-${String(gregorian.gm).padStart(2, "0")}-${String(gregorian.gd).padStart(2, "0")}`;
                console.log("Setting Gregorian string:", gregorianStr);
                currentJalali.jd = selectedDay;
                $calendar.find(".calendar-day").removeClass("selected").css("background-color", "").css("color", "");
                $(this).addClass("selected").css("background-color", "#007bff").css("color", "white");
                $input.val(jalaliStr);
                console.log("Hiding calendar...");
                $calendar.hide();
                setTimeout(() => {
                  console.log("Calling set_value...");
                  me.set_value(gregorianStr);
                }, 10);
              });
              $daysContainer.append($day);
            }
          };
          $calendar.find(".prev-year").on("click", () => {
            currentJalali.jy--;
            updateCalendar();
          });
          $calendar.find(".next-year").on("click", () => {
            currentJalali.jy++;
            updateCalendar();
          });
          $calendar.find(".prev-month").on("click", () => {
            if (currentJalali.jm === 1) {
              currentJalali.jm = 12;
              currentJalali.jy--;
            } else {
              currentJalali.jm--;
            }
            updateCalendar();
          });
          $calendar.find(".next-month").on("click", () => {
            if (currentJalali.jm === 12) {
              currentJalali.jm = 1;
              currentJalali.jy++;
            } else {
              currentJalali.jm++;
            }
            updateCalendar();
          });
          $calendar.find(".current-month-year").on("click", () => {
            const newYear = prompt("\u0633\u0627\u0644 \u062C\u062F\u06CC\u062F \u0631\u0627 \u0648\u0627\u0631\u062F \u06A9\u0646\u06CC\u062F:", currentJalali.jy);
            if (newYear && !isNaN(newYear) && newYear > 1300 && newYear < 1500) {
              currentJalali.jy = parseInt(newYear);
              updateCalendar();
            }
          });
          $calendar.find(".today-btn").on("click", () => {
            const today = new Date();
            const todayJalali = gToJ(today);
            currentJalali = { jy: todayJalali.jy, jm: todayJalali.jm, jd: todayJalali.jd };
            const jalaliStr = formatJalaliDate(todayJalali.jy, todayJalali.jm, todayJalali.jd);
            $input.val(jalaliStr);
            const gregorian = jToG(todayJalali.jy, todayJalali.jm, todayJalali.jd);
            const gregorianStr = `${gregorian.gy}-${String(gregorian.gm).padStart(2, "0")}-${String(gregorian.gd).padStart(2, "0")}`;
            me.set_value(gregorianStr);
            setTimeout(() => {
              if ($input.val() !== jalaliStr) {
                $input.val(jalaliStr);
              }
            }, 100);
            updateCalendar();
            $calendar.hide();
          });
          $input.on("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            const inputValue = $input.val();
            if (inputValue) {
              const jalali = parseJalaliDate(inputValue);
              if (jalali) {
                currentJalali = { jy: jalali.jy, jm: jalali.jm, jd: jalali.jd };
              }
            }
            updateCalendar();
            const inputRect = $input[0].getBoundingClientRect();
            $calendar.css({
              position: "fixed",
              top: inputRect.bottom + window.scrollY + 5,
              left: inputRect.left + window.scrollX,
              display: "block"
            });
          });
          $(document).on("click", (e) => {
            if (!$(e.target).closest(".jalali-calendar, .form-control").length) {
              $calendar.hide();
            }
          });
          updateCalendar();
        }
        set_formatted_input(value) {
          try {
            const r = super.set_formatted_input(value);
            if (value) {
              const gregorianDate = new Date(value + "T00:00:00Z");
              const jalali = gToJ(gregorianDate);
              const jalaliStr = formatJalaliDate(jalali.jy, jalali.jm, jalali.jd);
              console.log("set_formatted_input - Gregorian:", value, "Jalali:", jalaliStr);
              this.$input.val(jalaliStr);
              const $calendar = this.$input.siblings(".jalali-calendar");
              if ($calendar.length && !$calendar.is(":visible")) {
                const currentJalali = { jy: jalali.jy, jm: jalali.jm, jd: jalali.jd };
              }
            }
            return r;
          } catch (e) {
            console.log("set_formatted_input error:", e);
            return super.set_formatted_input(value);
          }
        }
      }
      class JalaliControlDatetime extends BaseControlDatetime {
        make_input() {
          this.$input = this.$wrapper.find("input");
          if (!this.$input.length) {
            this.$input = $(`<input class="form-control" type="text" readonly>`);
            this.$wrapper.append(this.$input);
          }
          this.$input.attr("readonly", false);
          this.createJalaliDatetimePicker();
        }
        createJalaliDatetimePicker() {
          const me = this;
          const $input = this.$input;
          const $picker = $(`
        <div class="jalali-datetime-picker" style="display: none; position: absolute; background: white; border: 1px solid #ccc; border-radius: 4px; padding: 10px; z-index: 1000; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
          <div class="calendar-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <button type="button" class="prev-month" style="background: none; border: none; cursor: pointer;">\u2039</button>
            <span class="current-month-year" style="font-weight: bold;"></span>
            <button type="button" class="next-month" style="background: none; border: none; cursor: pointer;">\u203A</button>
          </div>
          <div class="calendar-weekdays" style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; margin-bottom: 5px;">
            <div style="text-align: center; font-weight: bold; padding: 5px;">\u0634</div>
            <div style="text-align: center; font-weight: bold; padding: 5px;">\u06CC</div>
            <div style="text-align: center; font-weight: bold; padding: 5px;">\u062F</div>
            <div style="text-align: center; font-weight: bold; padding: 5px;">\u0633</div>
            <div style="text-align: center; font-weight: bold; padding: 5px;">\u0686</div>
            <div style="text-align: center; font-weight: bold; padding: 5px;">\u067E</div>
            <div style="text-align: center; font-weight: bold; padding: 5px;">\u062C</div>
          </div>
          <div class="calendar-days" style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; margin-bottom: 10px;"></div>
          <div class="time-picker" style="display: flex; gap: 10px; align-items: center; justify-content: center;">
            <input type="number" class="hour-input" min="0" max="23" placeholder="\u0633\u0627\u0639\u062A" style="width: 60px; padding: 5px; border: 1px solid #ccc; border-radius: 3px;">
            <span>:</span>
            <input type="number" class="minute-input" min="0" max="59" placeholder="\u062F\u0642\u06CC\u0642\u0647" style="width: 60px; padding: 5px; border: 1px solid #ccc; border-radius: 3px;">
          </div>
          <div class="picker-actions" style="display: flex; gap: 10px; justify-content: center; margin-top: 10px;">
            <button type="button" class="btn-ok" style="background: #007bff; color: white; border: none; padding: 5px 15px; border-radius: 3px; cursor: pointer;">\u062A\u0623\u06CC\u06CC\u062F</button>
            <button type="button" class="btn-cancel" style="background: #6c757d; color: white; border: none; padding: 5px 15px; border-radius: 3px; cursor: pointer;">\u0644\u063A\u0648</button>
          </div>
        </div>
      `);
          $input.after($picker);
          const now = new Date();
          let currentJalali = gToJ(now);
          let selectedTime = { hour: now.getHours(), minute: now.getMinutes() };
          const updateCalendar = () => {
            const monthNames = [
              "\u0641\u0631\u0648\u0631\u062F\u06CC\u0646",
              "\u0627\u0631\u062F\u06CC\u0628\u0647\u0634\u062A",
              "\u062E\u0631\u062F\u0627\u062F",
              "\u062A\u06CC\u0631",
              "\u0645\u0631\u062F\u0627\u062F",
              "\u0634\u0647\u0631\u06CC\u0648\u0631",
              "\u0645\u0647\u0631",
              "\u0622\u0628\u0627\u0646",
              "\u0622\u0630\u0631",
              "\u062F\u06CC",
              "\u0628\u0647\u0645\u0646",
              "\u0627\u0633\u0641\u0646\u062F"
            ];
            $picker.find(".current-month-year").text(`${monthNames[currentJalali.jm - 1]} ${currentJalali.jy}`);
            const daysInMonth = currentJalali.jm <= 6 ? 31 : currentJalali.jm <= 11 ? 30 : currentJalali.jy % 4 === 3 ? 30 : 29;
            const $daysContainer = $picker.find(".calendar-days");
            $daysContainer.empty();
            for (let day = 1; day <= daysInMonth; day++) {
              const $day = $(`<div class="calendar-day" data-day="${day}" style="text-align: center; padding: 8px; cursor: pointer; border-radius: 3px;">${day}</div>`);
              const inputValue = $input.val();
              if (inputValue) {
                const parts = inputValue.split(" ");
                if (parts.length === 2) {
                  const jalali = parseJalaliDate(parts[0]);
                  if (jalali && jalali.jy === currentJalali.jy && jalali.jm === currentJalali.jm && jalali.jd === day) {
                    $day.css("background-color", "#007bff").css("color", "white");
                  }
                }
              }
              $day.on("click", function() {
                const selectedDay = parseInt($(this).data("day"));
                currentJalali.jd = selectedDay;
                $picker.find(".hour-input").val(selectedTime.hour);
                $picker.find(".minute-input").val(selectedTime.minute);
                $picker.find(".calendar-day").removeClass("selected");
                $(this).addClass("selected");
              });
              $daysContainer.append($day);
            }
          };
          $picker.find(".prev-month").on("click", () => {
            if (currentJalali.jm === 1) {
              currentJalali.jm = 12;
              currentJalali.jy--;
            } else {
              currentJalali.jm--;
            }
            updateCalendar();
          });
          $picker.find(".next-month").on("click", () => {
            if (currentJalali.jm === 12) {
              currentJalali.jm = 1;
              currentJalali.jy++;
            } else {
              currentJalali.jm++;
            }
            updateCalendar();
          });
          $picker.find(".btn-ok").on("click", () => {
            const hour = parseInt($picker.find(".hour-input").val()) || 0;
            const minute = parseInt($picker.find(".minute-input").val()) || 0;
            const jalaliStr = `${formatJalaliDate(currentJalali.jy, currentJalali.jm, currentJalali.jd)} ${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
            $input.val(jalaliStr);
            const gregorian = jToG(currentJalali.jy, currentJalali.jm, currentJalali.jd);
            const gregorianStr = `${gregorian.gy}-${String(gregorian.gm).padStart(2, "0")}-${String(gregorian.gd).padStart(2, "0")} ${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}:00`;
            me.set_value(gregorianStr);
            $picker.hide();
          });
          $picker.find(".btn-cancel").on("click", () => {
            $picker.hide();
          });
          $input.on("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            const inputValue = $input.val();
            if (inputValue) {
              const parts = inputValue.split(" ");
              if (parts.length === 2) {
                const jalali = parseJalaliDate(parts[0]);
                if (jalali) {
                  currentJalali = { jy: jalali.jy, jm: jalali.jm, jd: jalali.jd };
                }
                const timeParts = parts[1].split(":");
                if (timeParts.length === 2) {
                  selectedTime.hour = parseInt(timeParts[0]) || 0;
                  selectedTime.minute = parseInt(timeParts[1]) || 0;
                }
              }
            }
            updateCalendar();
            const inputRect = $input[0].getBoundingClientRect();
            $picker.css({
              position: "fixed",
              top: inputRect.bottom + window.scrollY + 5,
              left: inputRect.left + window.scrollX,
              display: "block"
            });
          });
          $(document).on("click", (e) => {
            if (!$(e.target).closest(".jalali-datetime-picker, .form-control").length) {
              $picker.hide();
            }
          });
          updateCalendar();
        }
        set_formatted_input(value) {
          try {
            const r = super.set_formatted_input(value);
            if (value) {
              const gregorianDate = new Date(value + "Z");
              const jalali = gToJ(gregorianDate);
              const hh = String(gregorianDate.getHours()).padStart(2, "0");
              const mm = String(gregorianDate.getMinutes()).padStart(2, "0");
              const jalaliStr = `${formatJalaliDate(jalali.jy, jalali.jm, jalali.jd)} ${hh}:${mm}`;
              this.$input.val(jalaliStr);
            }
            return r;
          } catch (e) {
            return super.set_formatted_input(value);
          }
        }
      }
      frappe.ui.form.ControlDate = JalaliControlDate;
      frappe.ui.form.ControlDatetime = JalaliControlDatetime;
      console.log("ControlDate & ControlDatetime patched for Jalali");
      overrideControlsWhenReady();
    }
  })();

  // ../persian_calendar/persian_calendar/public/js/jalali_support/formatters.js
  (async function() {
    var _a, _b, _c, _d;
    let jalaliEnabled = false;
    try {
      const result = await frappe.call({ method: "persian_calendar.jalali_support.api.is_jalali_enabled" });
      jalaliEnabled = result && result.message;
      console.log("Jalali calendar enabled:", jalaliEnabled);
    } catch (e) {
      console.log("Error checking Jalali settings:", e);
      jalaliEnabled = false;
    }
    if (!jalaliEnabled) {
      console.log("Jalali calendar is disabled, skipping formatters");
      return;
    }
    function g2j_str(value) {
      try {
        const d = new Date(value + (value.length === 10 ? "T00:00:00Z" : "Z"));
        if (isNaN(d))
          return value;
        const j = toJalali(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate());
        return `${j.jy}-${String(j.jm).padStart(2, "0")}-${String(j.jd).padStart(2, "0")}`;
      } catch (e) {
        return value;
      }
    }
    const dt = frappe.datetime;
    const orig_str_to_user = (_a = dt.str_to_user) == null ? void 0 : _a.bind(dt);
    const orig_str_to_user_with_default = (_b = dt.str_to_user_with_default) == null ? void 0 : _b.bind(dt);
    const orig_format_date = (_c = dt.format_date) == null ? void 0 : _c.bind(dt);
    const orig_format_datetime = (_d = dt.format_datetime) == null ? void 0 : _d.bind(dt);
    if (orig_str_to_user) {
      dt.str_to_user = function(value) {
        if (!value)
          return value;
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
        if (!value)
          return value;
        return dt.str_to_user(value);
      };
    }
    if (orig_format_date) {
      dt.format_date = function(date_str) {
        return g2j_str(date_str);
      };
    }
    if (orig_format_datetime) {
      dt.format_datetime = function(value) {
        if (!value)
          return value;
        const date = value.slice(0, 10);
        const time = value.slice(11, 19) || "";
        return `${g2j_str(date)} ${time}`.trim();
      };
    }
    frappe.form.formatters.date = function(value, df, options, doc) {
      if (!value)
        return value;
      return g2j_str(value);
    };
    frappe.form.formatters.datetime = function(value, df, options, doc) {
      if (!value)
        return value;
      const d = new Date(value);
      if (isNaN(d))
        return value;
      const j = toJalali(d.getFullYear(), d.getMonth() + 1, d.getDate());
      const time = value.slice(11, 19) || "";
      return `${j.jy}-${String(j.jm).padStart(2, "0")}-${String(j.jd).padStart(2, "0")} ${time}`;
    };
  })();

  // ../persian_calendar/persian_calendar/public/js/jalali_support/auto_refresh.js
  (function() {
    function initAutoRefresh() {
      if (typeof frappe !== "undefined" && frappe.ui && frappe.ui.form) {
        frappe.ui.form.on("Jalali Settings", {
          refresh: function(frm) {
            frm.page.add_inner_button(__("Save & Reload"), function() {
              frm.save().then(function() {
                frappe.show_alert({
                  message: __("\u062A\u0646\u0638\u06CC\u0645\u0627\u062A \u0630\u062E\u06CC\u0631\u0647 \u0634\u062F. \u0635\u0641\u062D\u0647 \u062F\u0631 \u062D\u0627\u0644 \u0628\u0627\u0631\u06AF\u0630\u0627\u0631\u06CC \u0645\u062C\u062F\u062F..."),
                  indicator: "green"
                });
                setTimeout(function() {
                  window.location.reload();
                }, 1e3);
              });
            });
          },
          after_save: function(frm) {
            console.log("Jalali Settings after_save triggered");
            frappe.msgprint(__("\u062A\u0646\u0638\u06CC\u0645\u0627\u062A \u062A\u0642\u0648\u06CC\u0645 \u062C\u0644\u0627\u0644\u06CC \u0630\u062E\u06CC\u0631\u0647 \u0634\u062F. \u0635\u0641\u062D\u0647 \u062F\u0631 \u062D\u0627\u0644 \u0628\u0627\u0631\u06AF\u0630\u0627\u0631\u06CC \u0645\u062C\u062F\u062F..."));
            setTimeout(function() {
              window.location.reload();
            }, 1500);
          },
          onload: function(frm) {
            console.log("Jalali Settings onload triggered");
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
        setTimeout(initAutoRefresh, 100);
      }
    }
    initAutoRefresh();
  })();
})();
//# sourceMappingURL=jalali_support.bundle.PEGUJLI7.js.map
