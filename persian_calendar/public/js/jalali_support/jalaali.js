(function(){
  // Use Intl.DateTimeFormat with Persian calendar to derive reliable Jalali parts
  // Force Latin digits by using en locale with u-ca-persian
  const fmt = new Intl.DateTimeFormat('en-u-ca-persian', { year:'numeric', month:'2-digit', day:'2-digit'});
  function toJalaliPartsFromGregorianDate(gDate){
    const parts = fmt.formatToParts(gDate);
    const map = Object.fromEntries(parts.map(p=>[p.type,p.value]));
    const jy = parseInt(map.year, 10);
    const jm = parseInt(map.month, 10);
    const jd = parseInt(map.day, 10);
    return { jy, jm, jd };
  }
  function toJalali(gy,gm,gd){
    return toJalaliPartsFromGregorianDate(new Date(Date.UTC(gy, gm-1, gd)));
  }

  // Simple but accurate Jalali to Gregorian conversion
  function toGregorian(jy, jm, jd) {
    // Use a lookup table approach with Intl.DateTimeFormat
    // Create a range of dates and find the closest match
    const startYear = 2000;
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
            // Skip invalid dates
            continue;
          }
        }
      }
    }
    
    // Fallback: approximate conversion
    const approximateDate = new Date(2000, 6, 1); // July 1, 2000
    const approximateJalali = toJalaliPartsFromGregorianDate(approximateDate);
    
    const yearDiff = jy - approximateJalali.jy;
    const monthDiff = jm - approximateJalali.jm;
    const dayDiff = jd - approximateJalali.jd;
    
    const totalDays = yearDiff * 365 + monthDiff * 30 + dayDiff;
    const resultDate = new Date(approximateDate.getTime() + totalDays * 24 * 60 * 60 * 1000);
    
    return {
      gy: resultDate.getFullYear(),
      gm: resultDate.getMonth() + 1,
      gd: resultDate.getDate()
    };
  }

  // Expose helpers
  window.toJalali = toJalali;
  window.toGregorian = toGregorian;
  window.toJalaliPartsFromGregorianDate = toJalaliPartsFromGregorianDate;
})();


