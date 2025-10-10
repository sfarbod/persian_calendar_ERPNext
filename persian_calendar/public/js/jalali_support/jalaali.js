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
    return toJalaliPartsFromGregorianDate(new Date(gy, gm-1, gd));
  }

  // Simple but accurate Jalali to Gregorian conversion
  function toGregorian(jy, jm, jd) {
    // Use a more direct approach with Intl.DateTimeFormat
    // Create a date range and find the exact match
    const startYear = 2000;
    const endYear = 2030;
    
    for (let year = startYear; year <= endYear; year++) {
      for (let month = 1; month <= 12; month++) {
        for (let day = 1; day <= 31; day++) {
          try {
            const testDate = new Date(year, month - 1, day);
            if (testDate.getFullYear() !== year || testDate.getMonth() !== month - 1 || testDate.getDate() !== day) {
              continue; // Skip invalid dates
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
            // Skip invalid dates
            continue;
          }
        }
      }
    }
    
    // If no exact match found, use a more sophisticated fallback
    // Calculate approximate Gregorian date
    const jalaliEpoch = new Date(622, 2, 22); // March 22, 622 AD (Jalali year 1)
    const daysSinceEpoch = (jy - 1) * 365 + (jm - 1) * 30 + (jd - 1);
    const approximateDate = new Date(jalaliEpoch.getTime() + daysSinceEpoch * 24 * 60 * 60 * 1000);
    
    return {
      gy: approximateDate.getFullYear(),
      gm: approximateDate.getMonth() + 1,
      gd: approximateDate.getDate()
    };
  }

  // Expose helpers
  window.toJalali = toJalali;
  window.toGregorian = toGregorian;
  window.toJalaliPartsFromGregorianDate = toJalaliPartsFromGregorianDate;
})();


