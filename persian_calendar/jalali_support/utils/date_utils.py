

import datetime as dt
import jdatetime

def g_to_j(gdate: dt.date) -> jdatetime.date:
    return jdatetime.date.fromgregorian(date=gdate)

def j_to_g(jdate: jdatetime.date) -> dt.date:
    return jdate.togregorian()

def j_end_of_month(jdate: jdatetime.date) -> jdatetime.date:
    y, m = jdate.year, jdate.month
    if m <= 6:
        last = 31
    elif 7 <= m <= 11:
        last = 30
    else:
        last = 30 if jdatetime.j_isleap(y) else 29
    return jdatetime.date(y, m, last)

def is_j_month_end(gdate: dt.date) -> bool:
    j = g_to_j(gdate)
    return j == j_end_of_month(j)

def next_j_month_same_day(jdate: jdatetime.date) -> jdatetime.date:
    y, m, d = jdate.year, jdate.month, jdate.day
    m2 = 1 if m == 12 else (m + 1)
    y2 = y + 1 if m == 12 else y
    if m2 <= 6:
        last = 31
    elif 7 <= m2 <= 11:
        last = 30
    else:
        last = 30 if jdatetime.j_isleap(y2) else 29
    d2 = min(d, last)
    return jdatetime.date(y2, m2, d2)

def next_gregorian_for_j_month_end(gdate: dt.date) -> dt.date:
    j = g_to_j(gdate)
    nm = next_j_month_same_day(j)
    j_last = j_end_of_month(nm)
    return j_to_g(j_last)
