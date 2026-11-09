# AWS Hands-On Lab: Working with Functions

**Platform:** AWS Skill Builder (Vocareum)
**Date completed:** November 7, 2026
**Duration:** ~45 minutes
**Region:** US West (Oregon) — us-west-2

## Overview

This lab is a practical run through common SQL functions — aggregates, string functions, and `DISTINCT` — against the standard `world` sample database (`country`, `city`, `countrylanguage` tables) on a pre-built MariaDB instance.

**Scenario:** A pre-provisioned Command Host EC2 instance already has a `world` database loaded. The task is to connect to it and use built-in SQL functions to answer real questions about the data (population stats, region name parsing) rather than just running static queries.

## Objectives

- Connect to the lab's MariaDB instance via Session Manager
- Use aggregate functions (`SUM`, `AVG`, `MAX`, `MIN`, `COUNT`) on numeric data
- Use string functions (`SUBSTRING_INDEX`, `LENGTH`, `TRIM`) to parse and filter text
- Use `DISTINCT` to de-duplicate query results
- Solve a follow-up challenge applying the same string functions to a new case

## Architecture

```
EC2 "Command Host" (Session Manager, no SSH key)
     │  mysql client → MariaDB 10.5.29, logged in as root
     ▼
world database
 ├─ country          (population, region, GNP, etc.)
 ├─ city
 └─ countrylanguage
```

## Task 1: Connect to the Lab Environment

1. Opened a terminal session on the `Command Host` instance via **AWS Systems Manager → Session Manager** — no SSH key pair required.
2. Logged into the pre-installed MariaDB instance as `root`:
   ```
   Welcome to the MariaDB monitor.
   Server version: 10.5.29-MariaDB
   ```
3. Confirmed the `world` database was already loaded:
   ```sql
   SHOW DATABASES;
   ```

**Result:** Connected and ready to query `world.country`, `world.city`, and `world.countrylanguage`.

## Task 2: Use SQL Functions

1. **Aggregate functions on `Population`:**
   ```sql
   SELECT SUM(Population), AVG(Population), MAX(Population), MIN(Population), COUNT(Population)
   FROM country;
   ```
   | Function | Result |
   |---|---|
   | SUM | 6,078,749,450 |
   | AVG | 25,434,098.12 |
   | MAX | 1,277,558,000 |
   | MIN | 0 |
   | COUNT | 239 |

2. **`SUBSTRING_INDEX` to split and filter `Region` names** — pulled out everything before the first space to isolate compound region names, then filtered for rows starting with `"Southern..."`:
   ```sql
   SELECT Region FROM country WHERE SUBSTRING_INDEX(Region, ' ', 1) = 'Southern';
   ```
   Returned **34 rows**.

3. **`LENGTH(TRIM())` to find short region names** — trimmed whitespace, then filtered on string length to surface unusually short region labels:
   ```sql
   SELECT DISTINCT Region FROM country WHERE LENGTH(TRIM(Region)) < 10;
   ```
   Returned **39 rows** before de-duplication.

4. **`DISTINCT` to collapse to unique regions** — applying `DISTINCT` on the same short-name filter collapsed the 39 rows down to **3 unique regions**: Caribbean, Polynesia, Melanesia.

**Result:** All Task 2 queries run and verified against the expected row counts/values.

## Task 3: Challenge — Split a Compound Region Name

**Challenge:** The `Region` value `"Micronesia/Caribbean"` (belonging to the United States Minor Outlying Islands) packs two region names into one field, separated by `/`. Split it into two clean columns.

**Solution:**
```sql
SELECT Name,
       SUBSTRING_INDEX(Region, '/', 1) AS RegionPart1,
       SUBSTRING_INDEX(Region, '/', -1) AS RegionPart2
FROM country
WHERE Region = 'Micronesia/Caribbean';
```

- `SUBSTRING_INDEX(Region, '/', 1)` → everything before the first `/` → `Micronesia`
- `SUBSTRING_INDEX(Region, '/', -1)` → everything after the last `/` → `Caribbean`

**Result:** Correctly split `"Micronesia/Caribbean"` into two columns, matching **United States Minor Outlying Islands** as the row with that compound region.

## Verification Summary

| Step | Expected Result | Observed |
|---|---|---|
| Connect to MariaDB | Login succeeds as root | ✅ MariaDB 10.5.29 |
| `world` database present | Listed by SHOW DATABASES | ✅ Present |
| Aggregate functions | SUM/AVG/MAX/MIN/COUNT on Population | ✅ 6,078,749,450 / 25,434,098.12 / 1,277,558,000 / 0 / 239 |
| SUBSTRING_INDEX filter | "Southern..." regions | ✅ 34 rows |
| LENGTH(TRIM()) filter | Short region names | ✅ 39 rows |
| DISTINCT | Unique short regions | ✅ 3 rows (Caribbean, Polynesia, Melanesia) |
| Challenge | Split "Micronesia/Caribbean" | ✅ Matches United States Minor Outlying Islands |

## Key Takeaways

- **`SUBSTRING_INDEX(str, delim, count)` is the workhorse for splitting delimited text in SQL** — a positive count counts from the left, a negative count counts from the right, which is exactly what's needed to pull the "before" and "after" piece of a two-part field like `"Micronesia/Caribbean"` without knowing its length in advance.
- **`LENGTH(TRIM(x))` catches both whitespace noise and genuinely short values** — trimming before measuring length avoids false positives from padded strings.
- **`DISTINCT` is a de-duplication step, not a filter** — it ran *after* the `WHERE` clause narrowed the data down to short region names, then collapsed repeated values (39 rows → 3 unique regions).
- **Aggregate functions on a full column (no GROUP BY) collapse to a single summary row** — useful for quick sanity checks on a dataset (total/average/extremes/count) before writing more targeted queries.
- **Real-world data has messy compound fields** (like `"Micronesia/Caribbean"`) that look like one value but represent two — string functions are often the cleanest way to normalize that without rewriting the underlying data.

