**Title:** regex-log: two "invalid date" samples are rejected for their IP, so the date rules (and Feb 29) are never tested

**What the instruction requires**
> Assume that February can have up to 29 days in all years, without distinguishing leap years from non-leap years.

and, implicitly, that only real calendar dates match (April has 30 days).

**What passes today**
Both of these regexes pass `test_regex_matches_dates`:
- `feb-28-only/solve.sh`: the reference regex with February limited to `2[0-8]`. It rejects `2021-02-29`, which the instruction explicitly allows.
- `april-31-accepted/solve.sh`: the reference regex with 30-day months accepting day 31. It matches `2020-04-31`.

**Why the tests miss it**
- The samples commented `# N: invalid date 30th February` and `# N: invalid date 31th April` both use IP `172.16.0.256`, which is invalid, so they are rejected for the IP. With a valid date (`2000-04-10`) they are still rejected. They never exercise the date rule.
- No sample contains a February 29, a May date or a last octet of 250–254 on a matching line, so regexes that get these wrong also pass. (We saw passing variants that drop month `05` and reject octet `250`.)

**Suggested fix** (`test_fix.patch`): give the two samples a valid IP (`172.16.0.25`) and add `Leap-day login from 10.0.0.1 on 2021-02-29` and `Login from 10.0.0.250 on 2020-05-20` as matching lines.
Checked locally: the reference regex passes the patched test; both regexes above fail it.
