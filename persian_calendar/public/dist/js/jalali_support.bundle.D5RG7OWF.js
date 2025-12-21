(() => {
  var __defProp = Object.defineProperty;
  var __getOwnPropSymbols = Object.getOwnPropertySymbols;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __propIsEnum = Object.prototype.propertyIsEnumerable;
  var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
  var __spreadValues = (a, b) => {
    for (var prop in b || (b = {}))
      if (__hasOwnProp.call(b, prop))
        __defNormalProp(a, prop, b[prop]);
    if (__getOwnPropSymbols)
      for (var prop of __getOwnPropSymbols(b)) {
        if (__propIsEnum.call(b, prop))
          __defNormalProp(a, prop, b[prop]);
      }
    return a;
  };

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
      return toJalaliPartsFromGregorianDate(new Date(gy, gm - 1, gd));
    }
    function toGregorian2(jy, jm, jd) {
      const startYear = 2e3;
      const endYear = 2030;
      for (let year = startYear; year <= endYear; year++) {
        for (let month = 1; month <= 12; month++) {
          for (let day = 1; day <= 31; day++) {
            try {
              const testDate = new Date(year, month - 1, day);
              if (testDate.getFullYear() !== year || testDate.getMonth() !== month - 1 || testDate.getDate() !== day) {
                continue;
              }
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
      const jalaliEpoch = new Date(622, 2, 22);
      const daysSinceEpoch = (jy - 1) * 365 + (jm - 1) * 30 + (jd - 1);
      const approximateDate = new Date(jalaliEpoch.getTime() + daysSinceEpoch * 24 * 60 * 60 * 1e3);
      return {
        gy: approximateDate.getFullYear(),
        gm: approximateDate.getMonth() + 1,
        gd: approximateDate.getDate()
      };
    }
    window.toJalali = toJalali2;
    window.toGregorian = toGregorian2;
    window.toJalaliPartsFromGregorianDate = toJalaliPartsFromGregorianDate;
  })();

  // ../persian_calendar/persian_calendar/public/js/jalali_support/persian_calendar.js
  (function() {
    frappe.provide("frappe.ui.form");
    console.log("jalali_support script loaded");
    let jalaliEnabled = null;
    let EFFECTIVE_CALENDAR = {
      display_calendar: "Jalali",
      week_start: 6,
      week_end: 5
    };
    let FIRST_DAY = 6;
    let calendarSettingsCache = null;
    let calendarSettingsPromise = null;
    async function getCalendarSettings() {
      if (calendarSettingsCache !== null) {
        return calendarSettingsCache;
      }
      if (calendarSettingsPromise) {
        return calendarSettingsPromise;
      }
      calendarSettingsPromise = (async () => {
        try {
          const result = await frappe.call({ method: "persian_calendar.jalali_support.api.is_jalali_enabled" });
          jalaliEnabled = result && result.message;
          console.log("Jalali calendar enabled:", jalaliEnabled);
          if (!jalaliEnabled) {
            calendarSettingsCache = { enabled: false, calendar: { display_calendar: "Gregorian" } };
            return calendarSettingsCache;
          }
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
        } catch (e) {
          console.log("Error fetching calendar settings:", e);
          jalaliEnabled = false;
          calendarSettingsCache = { enabled: false, calendar: { display_calendar: "Gregorian" } };
          return calendarSettingsCache;
        }
      })();
      return calendarSettingsPromise;
    }
    getCalendarSettings();
    function gToJ(gDate) {
      if (typeof toJalali === "undefined" && typeof window.toJalali !== "undefined") {
        window.toJalali = window.toJalali;
      }
      if (typeof toJalali === "undefined") {
        console.error("toJalali function is not available! Make sure jalaali.js is loaded.");
        return { jy: 1400, jm: 1, jd: 1 };
      }
      return toJalali(gDate.getFullYear(), gDate.getMonth() + 1, gDate.getDate());
    }
    function jToG(jy, jm, jd) {
      if (typeof toGregorian === "undefined" && typeof window.toGregorian !== "undefined") {
        window.toGregorian = window.toGregorian;
      }
      if (typeof toGregorian === "undefined") {
        console.error("toGregorian function is not available! Make sure jalaali.js is loaded.");
        return { gy: 2021, gm: 1, gd: 1 };
      }
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
    function closeAllJalaliDatepickers() {
      $(".jalali-datepicker").each(function() {
        const $calendar = $(this);
        const instance = $calendar.data("jalaliDatepickerInstance");
        if (instance && instance.isOpen) {
          instance.close();
        } else {
          $calendar.hide();
        }
      });
      console.log("All Jalali datepickers closed");
    }
    class JalaliDatepicker {
      constructor(input, controlDate = null) {
        this.input = input;
        this.$input = $(input);
        this.controlDate = controlDate;
        this.isOpen = false;
        this.currentDate = gToJ(new Date());
        this.selectedDate = null;
        this.view = "days";
        this.yearRange = { start: 1400, end: 1410 };
        this.init();
      }
      init() {
        this.createCalendar();
        this.bindEvents();
        this.updateDisplay();
        this.fixAlignment();
        this.$calendar.data("jalaliDatepickerInstance", this);
      }
      fixAlignment() {
        const $input = this.$input;
        const $wrapper = $input.closest(".form-group, .frappe-control");
        const $formColumn = $input.closest(".form-column");
        if ($wrapper.length) {
          $wrapper.css({
            "margin-bottom": "0 !important",
            "padding": "0 !important",
            "vertical-align": "top !important",
            "display": "block !important",
            "position": "relative !important",
            "align-items": "flex-start !important"
          });
          $input.css({
            "height": "28px !important",
            "line-height": "28px !important",
            "padding": "6px 8px !important",
            "margin": "0 !important",
            "vertical-align": "top !important",
            "box-sizing": "border-box !important",
            "background-color": "#fff !important",
            "border": "1px solid #d1d8dd !important",
            "border-radius": "4px !important",
            "font-size": "13px !important",
            "font-weight": "normal !important",
            "color": "#36414c !important",
            "position": "relative !important",
            "z-index": "1 !important",
            "display": "block !important",
            "width": "100% !important",
            "font-family": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important'
          });
          const $inputContainer = $input.closest(".control-input, .form-control-wrapper");
          if ($inputContainer.length) {
            $inputContainer.css({
              "position": "relative !important",
              "display": "block !important",
              "margin": "0 !important",
              "padding": "0 !important",
              "vertical-align": "top !important",
              "align-items": "flex-start !important"
            });
          }
          if ($formColumn.length) {
            $formColumn.css({
              "vertical-align": "top !important",
              "display": "flex !important",
              "flex-direction": "column !important",
              "margin": "0 !important",
              "padding": "0 !important",
              "align-items": "stretch !important",
              "justify-content": "flex-start !important"
            });
          }
          const $formSection = $input.closest(".form-section");
          if ($formSection.length) {
            $formSection.css({
              "display": "flex !important",
              "flex-direction": "row !important",
              "align-items": "flex-start !important"
            });
          }
          if (this.$calendar && this.$calendar.length) {
            this.$calendar.css({
              "position": "absolute !important",
              "z-index": "9999 !important",
              "margin": "0 !important",
              "padding": "0 !important"
            });
          }
        }
      }
      createCalendar() {
        this.$input.siblings(".jalali-datepicker").remove();
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
            ">\u2039</button>
            <button type="button" class="nav-btn prev-decade" style="
              background: transparent;
              border: none;
              cursor: pointer;
              padding: 1px 3px;
              font-size: 11px;
              color: #6c7b7f;
              transition: color 0.2s ease;
              border-radius: 4px;
            ">\u2039\u2039</button>
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
            ">\u203A\u203A</button>
            <button type="button" class="nav-btn next-btn" style="
              background: transparent;
              border: none;
              cursor: pointer;
              padding: 1px 3px;
              font-size: 11px;
              color: #6c7b7f;
              transition: color 0.2s ease;
              border-radius: 4px;
            ">\u203A</button>
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
            ">\u0627\u0645\u0631\u0648\u0632</button>
          </div>
        </div>
      `;
        this.$calendar = $(calendarHTML);
        this.$input.after(this.$calendar);
        console.log("Jalali datepicker created");
      }
      bindEvents() {
        const self = this;
        this.$input.on("click", function(e) {
          e.preventDefault();
          e.stopPropagation();
          self.toggle();
        });
        this.$calendar.find(".prev-btn").on("click", function(e) {
          e.preventDefault();
          e.stopPropagation();
          self.navigateMonth(-1);
        });
        this.$calendar.find(".next-btn").on("click", function(e) {
          e.preventDefault();
          e.stopPropagation();
          self.navigateMonth(1);
        });
        this.$calendar.find(".month-year").on("click", function(e) {
          e.preventDefault();
          e.stopPropagation();
          if (self.view === "days") {
            self.showMonthsView();
          } else if (self.view === "months") {
            self.showYearsView();
          } else if (self.view === "years") {
            self.showMonthsView();
          }
        });
        this.$calendar.find(".prev-decade").on("click", function(e) {
          e.preventDefault();
          e.stopPropagation();
          self.navigateYear(-10);
        });
        this.$calendar.find(".next-decade").on("click", function(e) {
          e.preventDefault();
          e.stopPropagation();
          self.navigateYear(10);
        });
        this.$calendar.find(".today-btn").on("click", function(e) {
          e.preventDefault();
          e.stopPropagation();
          self.selectToday();
        });
        $(document).on("click.jalali-datepicker-global", function(e) {
          if (self.isOpen) {
            const $target = $(e.target);
            if (!$target.closest(".jalali-datepicker").length && !$target.is(self.input)) {
              console.log("Closing datepicker due to click outside");
              self.close();
            }
          }
        });
        $(document).on("click.jalali-datepicker-date-inputs", function(e) {
          if (self.isOpen) {
            const $target = $(e.target);
            if ($target.is('input[data-fieldtype="Date"]') && !$target.is(self.input)) {
              console.log("Closing datepicker due to click on another date field");
              self.close();
            }
          }
        });
        this._keydownHandler = function(e) {
          if (e.keyCode === 27 && self.isOpen) {
            self.close();
          }
        };
        $(document).on("keydown.jalali-datepicker-" + (this.input.id || "default"), this._keydownHandler);
        this._globalClickListener = function(e) {
          if (self.isOpen) {
            const $target = $(e.target);
            const isClickInsideDatepicker = $target.closest(".jalali-datepicker").length > 0;
            const isClickOnOwnInput = $target.is(self.input);
            if (!isClickInsideDatepicker && !isClickOnOwnInput) {
              console.log("Capturing phase: Closing datepicker due to click outside (general)");
              self.close();
            }
          }
        };
        document.addEventListener("click", this._globalClickListener, true);
        this.$calendar.find(".nav-btn").hover(
          function() {
            $(this).css("background-color", "#f8f9fa");
          },
          function() {
            $(this).css("background-color", "transparent");
          }
        );
        this.$calendar.find(".month-year").hover(
          function() {
            $(this).css("background-color", "#f8f9fa");
          },
          function() {
            $(this).css("background-color", "transparent");
          }
        );
      }
      toggle() {
        if (this.isOpen) {
          this.close();
        } else {
          this.view = "days";
          this.open();
        }
      }
      open() {
        closeAllJalaliDatepickers();
        this.isOpen = true;
        this.view = "days";
        this.updateDisplay();
        this.updateCalendar();
        this.$calendar.show();
        console.log("Calendar opened with view:", this.view);
      }
      close() {
        this.isOpen = false;
        this.$calendar.hide();
        if (this._keydownHandler) {
          $(document).off("keydown.jalali-datepicker-" + (this.input.id || "default"), this._keydownHandler);
          this._keydownHandler = null;
        }
        if (this._globalClickListener) {
          document.removeEventListener("click", this._globalClickListener, true);
          this._globalClickListener = null;
        }
        console.log("Calendar closed");
      }
      navigateMonth(direction) {
        if (this.view === "days") {
          this.currentDate.jm += direction;
          if (this.currentDate.jm > 12) {
            this.currentDate.jm = 1;
            this.currentDate.jy++;
          } else if (this.currentDate.jm < 1) {
            this.currentDate.jm = 12;
            this.currentDate.jy--;
          }
          this.updateCalendar();
        } else if (this.view === "months") {
          this.currentDate.jy += direction;
          this.updateMonthsView();
        }
      }
      navigateYear(direction) {
        this.yearRange.start += direction;
        this.yearRange.end += direction;
        this.currentDate.jy = this.yearRange.start + 4;
        this.updateYearsView();
      }
      showMonthsView() {
        this.view = "months";
        this.updateMonthsView();
        this.$calendar.find(".days-view").hide();
        this.$calendar.find(".years-view").hide();
        this.$calendar.find(".months-view").show();
      }
      showYearsView() {
        this.view = "years";
        this.updateYearsView();
        this.$calendar.find(".days-view").hide();
        this.$calendar.find(".months-view").hide();
        this.$calendar.find(".years-view").show();
      }
      showDaysView() {
        this.view = "days";
        this.updateCalendar();
        this.$calendar.find(".months-view").hide();
        this.$calendar.find(".years-view").hide();
        this.$calendar.find(".days-view").show();
      }
      updateCalendar() {
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
        this.$calendar.find(".month-year").text(`${monthNames[this.currentDate.jm - 1]} ${this.currentDate.jy}`);
        this.$calendar.find(".prev-btn, .next-btn").show();
        this.$calendar.find(".prev-decade, .next-decade").hide();
        this.$calendar.find(".days-view").hide();
        this.$calendar.find(".months-view").hide();
        this.$calendar.find(".years-view").hide();
        if (this.view === "days") {
          this.$calendar.find(".days-view").show();
          this.updateWeekdays();
          this.updateDays();
        } else if (this.view === "months") {
          this.$calendar.find(".months-view").show();
          this.updateMonthsView();
        } else if (this.view === "years") {
          this.$calendar.find(".years-view").show();
          this.updateYearsView();
        }
      }
      updateWeekdays() {
        const weekdayNames = ["\u06CC", "\u062F", "\u0633", "\u0686", "\u067E", "\u062C", "\u0634"];
        const $weekdaysContainer = this.$calendar.find(".weekdays");
        $weekdaysContainer.empty();
        for (let i = 0; i < 7; i++) {
          const dayIndex = (FIRST_DAY + i) % 7;
          $weekdaysContainer.append($(`<div class="weekday" style="text-align: center; padding: 0; font-weight: 500; font-size: 9px; color: var(--text-light, #7c7c7c); font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif); width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;">${weekdayNames[dayIndex]}</div>`));
        }
      }
      updateDays() {
        const $daysGrid = this.$calendar.find(".days-grid");
        $daysGrid.empty();
        const daysInMonth = this.currentDate.jm <= 6 ? 31 : this.currentDate.jm <= 11 ? 30 : this.currentDate.jy % 4 === 3 ? 30 : 29;
        const firstDay = this.getFirstDayOfMonth(this.currentDate.jy, this.currentDate.jm);
        let prevMonth = this.currentDate.jm - 1;
        let prevYear = this.currentDate.jy;
        if (prevMonth < 1) {
          prevMonth = 12;
          prevYear--;
        }
        const prevMonthDays = prevMonth <= 6 ? 31 : prevMonth <= 11 ? 30 : prevYear % 4 === 3 ? 30 : 29;
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
          $prevDay.on("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.currentDate.jy = prevYear;
            this.currentDate.jm = prevMonth;
            this.currentDate.jd = day;
            this.selectDate(day);
          });
          $prevDay.hover(
            function() {
              $(this).css("background-color", "#f8f9fa");
            },
            function() {
              $(this).css("background-color", "transparent");
            }
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
          $day.on("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.selectDate(day);
          });
          $day.hover(
            function() {
              if (!$(this).hasClass("selected") && !$(this).hasClass("today")) {
                $(this).css("background-color", "#f8f9fa");
              }
            },
            function() {
              if (!$(this).hasClass("selected") && !$(this).hasClass("today")) {
                $(this).css("background-color", "transparent");
              }
            }
          );
          const today = gToJ(new Date());
          if (this.currentDate.jy === today.jy && this.currentDate.jm === today.jm && day === today.jd) {
            $day.addClass("today").css({
              "background-color": "var(--control-bg, #f3f3f3)",
              "color": "var(--text-color, #36414c)",
              "font-weight": "bold"
            });
          }
          if (this.selectedDate && this.selectedDate.jy === this.currentDate.jy && this.selectedDate.jm === this.currentDate.jm && this.selectedDate.jd === day) {
            $day.addClass("selected").css({
              "background-color": "var(--primary, #171717)",
              "color": "var(--bg-color, white)",
              "font-weight": "bold"
            });
          }
          $daysGrid.append($day);
        }
        let nextMonth = this.currentDate.jm + 1;
        let nextYear = this.currentDate.jy;
        if (nextMonth > 12) {
          nextMonth = 1;
          nextYear++;
        }
        const totalCells = 42;
        const currentCells = firstDay + daysInMonth;
        const remainingCells = totalCells - currentCells;
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
          $nextDay.on("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.currentDate.jy = nextYear;
            this.currentDate.jm = nextMonth;
            this.currentDate.jd = day;
            this.selectDate(day);
          });
          $nextDay.hover(
            function() {
              $(this).css("background-color", "#f8f9fa");
            },
            function() {
              $(this).css("background-color", "transparent");
            }
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
        const gregorian = jToG(this.selectedDate.jy, this.selectedDate.jm, this.selectedDate.jd);
        const gregorianStr = `${gregorian.gy}-${String(gregorian.gm).padStart(2, "0")}-${String(gregorian.gd).padStart(2, "0")}`;
        console.log(`Converting Jalali ${jalaliStr} to Gregorian ${gregorianStr}`);
        if (this.controlDate && this.controlDate.set_value) {
          this.controlDate.set_value(gregorianStr);
          this.$input.val(jalaliStr);
        } else {
          this.$input.val(jalaliStr);
          this.$input.trigger("change");
        }
        this.close();
        console.log(`Selected date: ${jalaliStr} (${gregorianStr})`);
      }
      selectToday() {
        const today = gToJ(new Date());
        console.log("Today in Jalali:", today);
        this.currentDate = __spreadValues({}, today);
        this.view = "days";
        this.updateCalendar();
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
            this.currentDate = __spreadValues({}, jalali);
          }
        }
        this.view = "days";
      }
      updateMonthsView() {
        this.$calendar.find(".month-year").text(`${this.currentDate.jy}`);
        this.$calendar.find(".prev-btn, .next-btn").show();
        this.$calendar.find(".prev-decade, .next-decade").hide();
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
        const $monthsGrid = this.$calendar.find(".months-grid");
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
          $month.on("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.currentDate.jm = index + 1;
            this.showDaysView();
          });
          $month.hover(
            function() {
              if (!$(this).hasClass("selected")) {
                $(this).css("background-color", "#f8f9fa");
              }
            },
            function() {
              if (!$(this).hasClass("selected")) {
                $(this).css("background-color", "transparent");
              }
            }
          );
          if (this.currentDate.jm === index + 1) {
            $month.addClass("selected").css({
              "background-color": "var(--primary, #171717)",
              "color": "var(--bg-color, white)",
              "font-weight": "bold"
            });
          }
          $monthsGrid.append($month);
        });
      }
      updateYearsView() {
        const currentYear = this.currentDate.jy;
        const startYear = Math.floor(currentYear / 10) * 10;
        const endYear = startYear + 9;
        this.yearRange = { start: startYear, end: endYear };
        this.$calendar.find(".month-year").text(`${this.yearRange.start} - ${this.yearRange.end}`);
        this.$calendar.find(".prev-btn, .next-btn").hide();
        this.$calendar.find(".prev-decade, .next-decade").show();
        const $yearsGrid = this.$calendar.find(".years-grid");
        $yearsGrid.empty();
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
          $year.on("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.currentDate.jy = year;
            this.showMonthsView();
          });
          $year.hover(
            function() {
              if (!$(this).hasClass("selected")) {
                $(this).css("background-color", "#f8f9fa");
              }
            },
            function() {
              if (!$(this).hasClass("selected")) {
                $(this).css("background-color", "transparent");
              }
            }
          );
          if (this.currentDate.jy === year) {
            $year.addClass("selected").css({
              "background-color": "var(--primary, #171717) !important",
              "color": "var(--bg-color, white) !important",
              "font-weight": "bold !important"
            });
          }
          if (year < startYear || year > endYear) {
            $year.addClass("other-decade").css({
              "color": "var(--text-light, #999) !important",
              "cursor": "not-allowed !important",
              "opacity": "0.4 !important"
            });
            $year.off("click").on("click", (e) => {
              e.preventDefault();
              e.stopPropagation();
            });
            $year.off("mouseenter mouseleave");
          }
          $yearsGrid.append($year);
        }
      }
      getFirstDayOfMonth(year, month) {
        const gregorian = jToG(year, month, 1);
        const date = new Date(gregorian.gy, gregorian.gm - 1, gregorian.gd);
        const jsWeekday = date.getDay();
        return (jsWeekday + 1) % 7;
      }
    }
    function overrideControlsWhenReady() {
      const hasControls = frappe && frappe.ui && frappe.ui.form && frappe.ui.form.ControlDate;
      if (!hasControls) {
        setTimeout(overrideControlsWhenReady, 50);
        return;
      }
      if (frappe.ui.form.ControlDate.prototype.replaceWithJalaliDatepicker) {
        console.log("ControlDate already patched for Jalali");
        return;
      }
      const BaseControlDate = frappe.ui.form.ControlDate;
      class JalaliControlDate extends BaseControlDate {
        make_input() {
          var _a, _b;
          super.make_input();
          let useJalali = true;
          let display_calendar = "Jalali";
          if (calendarSettingsCache !== null) {
            useJalali = calendarSettingsCache.enabled && ((_a = calendarSettingsCache.calendar) == null ? void 0 : _a.display_calendar) !== "Gregorian";
            display_calendar = ((_b = calendarSettingsCache.calendar) == null ? void 0 : _b.display_calendar) || "Jalali";
            if (calendarSettingsCache.calendar) {
              EFFECTIVE_CALENDAR = calendarSettingsCache.calendar;
            }
            if (calendarSettingsCache.firstDay !== void 0) {
              FIRST_DAY = calendarSettingsCache.firstDay;
            }
          } else {
            getCalendarSettings().then((settings) => {
              var _a2;
              if (!settings.enabled || ((_a2 = settings.calendar) == null ? void 0 : _a2.display_calendar) === "Gregorian") {
                if (this.jalaliDatepicker) {
                  this.removeAirDatepickerInstances();
                  this.jalaliDatepicker = null;
                  super.make_input();
                }
              } else {
                if (settings.calendar) {
                  EFFECTIVE_CALENDAR = settings.calendar;
                }
                if (settings.firstDay !== void 0) {
                  FIRST_DAY = settings.firstDay;
                }
                if (this.jalaliDatepicker) {
                  this.jalaliDatepicker.updateDisplay();
                }
              }
            });
          }
          this.display_calendar = display_calendar;
          if (useJalali) {
            this.replaceWithJalaliDatepicker();
          }
        }
        replaceWithJalaliDatepicker() {
          this.$input = this.$wrapper.find("input");
          if (!this.$input.length) {
            this.$input = $(`<input class="form-control" type="text">`);
            this.$wrapper.append(this.$input);
          }
          this.removeAirDatepickerInstances();
          this.$input.removeAttr("data-date-format");
          this.$input.removeAttr("data-alt-input");
          this.$input.removeAttr("data-alt-format");
          this.$input.removeClass("datepicker-input");
          this.$input.removeClass("hasDatepicker");
          this.$input.attr("readonly", false);
          this.$input.css({
            "height": "var(--input-height) !important",
            "line-height": "var(--input-height) !important",
            "padding": "var(--input-padding) !important",
            "margin": "0 !important",
            "vertical-align": "top !important",
            "box-sizing": "border-box !important",
            "background-color": "var(--control-bg) !important",
            "border": "1px solid var(--border-color) !important",
            "border-radius": "var(--border-radius-sm) !important",
            "font-size": "var(--text-base) !important",
            "font-weight": "var(--font-weight-regular) !important",
            "color": "var(--text-color) !important",
            "position": "relative !important",
            "z-index": "1 !important",
            "display": "block !important",
            "width": "100% !important"
          });
          const $controlInputWrapper = this.$wrapper.find(".control-input-wrapper");
          if ($controlInputWrapper.length) {
            $controlInputWrapper.css({
              "margin": "0 !important",
              "padding": "0 !important",
              "vertical-align": "top !important",
              "display": "block !important",
              "position": "relative !important"
            });
          }
          const $controlInput = this.$wrapper.find(".control-input");
          if ($controlInput.length) {
            $controlInput.css({
              "margin": "0 !important",
              "padding": "0 !important",
              "vertical-align": "top !important",
              "display": "block !important",
              "position": "relative !important",
              "height": "var(--input-height) !important",
              "line-height": "var(--input-height) !important"
            });
          }
          this.$wrapper.css({
            "margin": "0 !important",
            "padding": "0 !important",
            "vertical-align": "top !important",
            "display": "block !important",
            "position": "relative !important",
            "align-items": "flex-start !important"
          });
          const $formColumn = this.$input.closest(".form-column");
          if ($formColumn.length) {
            $formColumn.css({
              "vertical-align": "top !important",
              "display": "flex !important",
              "flex-direction": "column !important",
              "margin": "0 !important",
              "padding": "0 !important",
              "align-items": "stretch !important",
              "justify-content": "flex-start !important"
            });
          }
          const $formSection = this.$input.closest(".form-section");
          if ($formSection.length) {
            $formSection.css({
              "display": "flex !important",
              "flex-direction": "row !important",
              "align-items": "flex-start !important"
            });
          }
          this.removeAirDatepickerInstances();
          this.jalaliDatepicker = new JalaliDatepicker(this.$input[0], this);
          this.fixFieldAlignment();
        }
        fixFieldAlignment() {
          const $formGroup = this.$wrapper.find(".form-group");
          if ($formGroup.length) {
            $formGroup.css({
              "margin-bottom": "0 !important",
              "padding": "0 !important",
              "vertical-align": "top !important",
              "display": "block !important"
            });
          }
          const $clearfix = this.$wrapper.find(".clearfix");
          if ($clearfix.length) {
            $clearfix.css({
              "margin": "0 !important",
              "padding": "0 !important",
              "vertical-align": "top !important",
              "display": "block !important"
            });
          }
          const $controlLabel = this.$wrapper.find(".control-label");
          if ($controlLabel.length) {
            $controlLabel.css({
              "margin": "0 !important",
              "padding": "0 !important",
              "vertical-align": "top !important",
              "display": "block !important",
              "line-height": "normal !important"
            });
          }
          const $help = this.$wrapper.find(".help");
          if ($help.length) {
            $help.css({
              "margin": "0 !important",
              "padding": "0 !important",
              "vertical-align": "top !important",
              "display": "block !important"
            });
          }
          const $helpBox = this.$wrapper.find(".help-box");
          if ($helpBox.length) {
            $helpBox.css({
              "margin": "0 !important",
              "padding": "0 !important",
              "vertical-align": "top !important",
              "display": "block !important"
            });
          }
        }
        removeAirDatepickerInstances() {
          if (this.datepicker) {
            try {
              this.datepicker.destroy();
              this.datepicker = null;
            } catch (e) {
              console.log("Error destroying air-datepicker:", e);
            }
          }
          $(".air-datepicker").remove();
          $(".datepicker-input").removeClass("datepicker-input");
          $(".hasDatepicker").removeClass("hasDatepicker");
          $(".datepicker-icon").remove();
          $(".datepicker-btn").remove();
          if (this.$input && this.$input.length) {
            this.$input.removeData("datepicker");
          }
          if (this.$input && this.$input.length) {
            this.$input.off(".datepicker");
          }
          console.log("Air-datepicker instances removed for field:", this.df.fieldname);
        }
        set_formatted_input(value) {
          var _a;
          try {
            const useJalali = calendarSettingsCache === null || calendarSettingsCache.enabled && ((_a = calendarSettingsCache.calendar) == null ? void 0 : _a.display_calendar) !== "Gregorian";
            let display_calendar = this.display_calendar;
            if (!display_calendar) {
              if (calendarSettingsCache && calendarSettingsCache.calendar) {
                display_calendar = calendarSettingsCache.calendar.display_calendar;
              } else {
                display_calendar = EFFECTIVE_CALENDAR && EFFECTIVE_CALENDAR.display_calendar || "Jalali";
              }
            }
            if (!useJalali || display_calendar === "Gregorian") {
              console.log("set_formatted_input - Using Gregorian calendar, no conversion");
              return super.set_formatted_input(value);
            }
            const r = super.set_formatted_input(value);
            if (value) {
              console.log("set_formatted_input - Input value:", value, "Display calendar:", display_calendar);
              let gregorianDate;
              if (typeof value === "string") {
                if (value.includes("T")) {
                  gregorianDate = new Date(value);
                } else if (value.includes("-")) {
                  gregorianDate = new Date(value + "T00:00:00");
                } else {
                  gregorianDate = new Date(value);
                }
              } else {
                gregorianDate = new Date(value);
              }
              console.log("set_formatted_input - Parsed date:", gregorianDate);
              if (!isNaN(gregorianDate.getTime())) {
                const jalali = gToJ(gregorianDate);
                const jalaliStr = formatJalaliDate(jalali.jy, jalali.jm, jalali.jd);
                console.log("set_formatted_input - Jalali:", jalali, "String:", jalaliStr);
                this.$input.val(jalaliStr);
                if (this.jalaliDatepicker) {
                  this.jalaliDatepicker.updateDisplay();
                }
              } else {
                console.log("set_formatted_input - Invalid date, keeping original value");
              }
            }
            return r;
          } catch (e) {
            console.log("set_formatted_input error:", e);
            return super.set_formatted_input(value);
          }
        }
      }
      frappe.ui.form.ControlDate = JalaliControlDate;
      console.log("ControlDate patched for Jalali");
    }
    function removeAllAirDatepickerInstances() {
      $(".air-datepicker").remove();
      $("input.datepicker-input, input.hasDatepicker").each(function() {
        $(this).removeClass("datepicker-input hasDatepicker");
        $(this).removeAttr("data-date-format");
        $(this).removeAttr("data-alt-input");
        $(this).removeAttr("data-alt-format");
        $(this).removeData("datepicker");
        $(this).off(".datepicker");
      });
      $(".datepicker-icon, .datepicker-btn").remove();
      if (window.Datepicker) {
        try {
          Object.keys(window.Datepicker.instances || {}).forEach((key) => {
            try {
              window.Datepicker.instances[key].destroy();
            } catch (e) {
              console.log("Error destroying air-datepicker instance:", e);
            }
          });
        } catch (e) {
          console.log("Error accessing air-datepicker instances:", e);
        }
      }
      console.log("Removed all air-datepicker instances from the page");
    }
    removeAllAirDatepickerInstances();
    setInterval(removeAllAirDatepickerInstances, 1e3);
    overrideControlsWhenReady();
    try {
      frappe.ui.form.on("Fiscal Year", {
        onload: async function(frm) {
          try {
            if (!frm.doc.__islocal)
              return;
            const settings = await getCalendarSettings();
            if (!settings.enabled)
              return;
            if (settings.calendar && settings.calendar.display_calendar === "Gregorian")
              return;
            if (frm.doc.year_start_date)
              return;
            const todayG = new Date();
            const todayJ = gToJ(todayG);
            const jy = todayJ.jy;
            const startG = jToG(jy, 1, 1);
            const startStr = `${startG.gy}-${String(startG.gm).padStart(2, "0")}-${String(startG.gd).padStart(2, "0")}`;
            const nextStartG = jToG(jy + 1, 1, 1);
            const nextStartDate = new Date(nextStartG.gy, nextStartG.gm - 1, nextStartG.gd);
            const endDate = new Date(nextStartDate.getTime() - 24 * 60 * 60 * 1e3);
            const endStr = `${endDate.getFullYear()}-${String(endDate.getMonth() + 1).padStart(2, "0")}-${String(endDate.getDate()).padStart(2, "0")}`;
            frm.set_value("year_start_date", startStr);
            frm.set_value("year_end_date", endStr);
          } catch (e) {
            console.log("Error setting Jalali Fiscal Year defaults:", e);
          }
        }
      });
    } catch (e) {
      console.log("Unable to attach Fiscal Year onload override:", e);
    }
    try {
      frappe.ui.form.on("User", {
        after_save: function(frm) {
          if (frm.doc.calendar_preference !== void 0 && frm.doc.name === frappe.session.user) {
            console.log("User calendar_preference changed to:", frm.doc.calendar_preference);
            console.log("Reloading page to apply new calendar settings...");
            setTimeout(function() {
              window.location.reload();
            }, 500);
          }
        }
      });
    } catch (e) {
      console.log("Unable to attach User form handler:", e);
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
    } catch (e) {
      console.log("Error fetching effective calendar in formatters:", e);
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
    function shouldConvertToJalali() {
      return EFFECTIVE_CALENDAR && EFFECTIVE_CALENDAR.display_calendar === "Jalali";
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
        if (!shouldConvertToJalali()) {
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
        if (!value)
          return value;
        if (!shouldConvertToJalali()) {
          return orig_str_to_user_with_default(value);
        }
        return dt.str_to_user(value);
      };
    }
    if (orig_format_date) {
      dt.format_date = function(date_str) {
        if (!shouldConvertToJalali()) {
          return orig_format_date(date_str);
        }
        return g2j_str(date_str);
      };
    }
    if (orig_format_datetime) {
      dt.format_datetime = function(value) {
        if (!value)
          return value;
        if (!shouldConvertToJalali()) {
          return orig_format_datetime(value);
        }
        const date = value.slice(0, 10);
        const time = value.slice(11, 19) || "";
        return `${g2j_str(date)} ${time}`.trim();
      };
    }
    const orig_date_formatter = frappe.form.formatters.date;
    const orig_datetime_formatter = frappe.form.formatters.datetime;
    frappe.form.formatters.date = function(value, df, options, doc) {
      if (!value)
        return value;
      if (!shouldConvertToJalali()) {
        if (orig_date_formatter) {
          return orig_date_formatter(value, df, options, doc);
        }
        return value;
      }
      return g2j_str(value);
    };
    frappe.form.formatters.datetime = function(value, df, options, doc) {
      if (!value)
        return value;
      if (!shouldConvertToJalali()) {
        if (orig_datetime_formatter) {
          return orig_datetime_formatter(value, df, options, doc);
        }
        return value;
      }
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
          after_save: function(frm) {
            setTimeout(function() {
              window.location.reload();
            }, 100);
          }
        });
      } else {
        setTimeout(initAutoRefresh, 100);
      }
    }
    initAutoRefresh();
  })();
})();
//# sourceMappingURL=jalali_support.bundle.D5RG7OWF.js.map
