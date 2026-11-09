# AWS Hands-On Lab: Selecting Data from a Database

**Platform:** AWS Skill Builder (Vocareum)
**Date completed:** November 9, 2026
**Duration:** ~45 minutes
**Region:** US West (Oregon) — us-west-2

## Overview

This lab is a first-principles walkthrough of the SQL `SELECT` statement and the core comparison/filtering operators, run against the standard `world` sample database (`country`, `city`, `countrylanguage` tables) on a pre-built MariaDB instance.

**Scenario:** The database operations team has a relational database named `world` containing three tables: `city`, `country`, and `countrylanguage`. The task is to write a series of queries against `country`, progressively layering on column selection, aliasing, sorting, and filtering, then apply the same techniques to answer a specific business question.

## Objectives

- Use the `SELECT` statement to query a database
- Use the `COUNT()` function
- Use the following operators to query a database: `<`, `>`, `=`, `WHERE`, `ORDER BY`, `AND`

## Architecture

```
EC2 "Command Host" (Session Manager, no SSH key)
     │  mysql client → MariaDB 10.5.29, logged in as root
          ▼
          world database
           ├─ country          (Name, Capital, Region, SurfaceArea, Population, ...)
            ├─ city
             └─ countrylanguage
             ```

             ## Task 1: Connect to the Command Host

             1. Opened a terminal session on the `Command Host` instance via **EC2 → Instances → Connect → Session Manager** — no SSH key pair required.
             2. Elevated to root and moved to the working directory:
                ```
                   sudo su
                      cd /home/ec2-user/
                         ```
                         3. Logged into the pre-installed MariaDB instance as `root` using the password supplied in the lab instructions:
                            ```
                               Welcome to the MariaDB monitor.
                                  Server version: 10.5.29-MariaDB
                                     ```

                                     **Result:** Connected and ready to query `world.country`, `world.city`, and `world.countrylanguage`.

                                     ## Task 2: Query the world Database

                                     1. **Confirmed the database exists:**
                                        ```sql
                                           SHOW DATABASES;
                                              ```
                                                 Returned `information_schema`, `mysql`, `performance_schema`, and `world`.

                                                 2. **Listed all rows/columns and counted rows in `country`:**
                                                    ```sql
                                                       SELECT * FROM world.country;
                                                          SELECT COUNT(*) FROM world.country;
                                                             ```
                                                                `COUNT(*)` returned **239** rows.

                                                                3. **Inspected the table schema:**
                                                                   ```sql
                                                                      SHOW COLUMNS FROM world.country;
                                                                         ```
                                                                            14 columns, including `Name`, `Capital`, `Region`, `SurfaceArea`, and `Population`.

                                                                            4. **Selected specific columns with a descriptive alias, sorted by population:**
                                                                               ```sql
                                                                                  SELECT Name, Capital, Region, SurfaceArea AS "Surface Area", Population
                                                                                     FROM world.country
                                                                                        ORDER BY Population DESC
                                                                                           LIMIT 10;
                                                                                              ```
                                                                                                 Top result: **China**, population 1,277,558,000, surface area 9,572,900.00 km².

                                                                                                 5. **Filtered with `WHERE` and a compound `AND` condition** — all countries with population strictly between 50,000,000 and 100,000,000:
                                                                                                    ```sql
                                                                                                       SELECT Name, Capital, Region, SurfaceArea AS "Surface Area", Population
                                                                                                          FROM world.country
                                                                                                             WHERE Population > 50000000 AND Population < 100000000
                                                                                                                ORDER BY Population DESC;
                                                                                                                   ```
                                                                                                                      Returned **14 rows**, from Mexico (98,881,000) down to Ukraine (50,456,000).
                                                                                                                      
                                                                                                                      **Result:** All Task 2 queries ran and returned the expected row counts (239 total countries, 14 in the 50M–100M population band).
                                                                                                                      
                                                                                                                      ## Task 3: Challenge — Southern Europe Population Query
                                                                                                                      
                                                                                                                      **Challenge:** Which country in Southern Europe has a population greater than 50,000,000?
                                                                                                                      
                                                                                                                      **Solution:**
                                                                                                                      ```sql
                                                                                                                      SELECT Name, Capital, Region, SurfaceArea AS "Surface Area", Population
                                                                                                                      FROM world.country
                                                                                                                      WHERE Population > 50000000 AND Region = "Southern Europe";
                                                                                                                      ```
                                                                                                                      
                                                                                                                      **Result:** Returned exactly one row — **Italy** (capital code 1464, surface area 301,316.00 km², population 57,680,000) — matching the lab's own answer key.
                                                                                                                      
                                                                                                                      ## Verification Summary
                                                                                                                      
                                                                                                                      | Step | Expected Result | Observed |
                                                                                                                      |---|---|---|
                                                                                                                      | Connect to MariaDB | Login succeeds as root | ✅ MariaDB 10.5.29 |
                                                                                                                      | `world` database present | Listed by `SHOW DATABASES` | ✅ Present |
                                                                                                                      | Row count, `country` table | `COUNT(*)` | ✅ 239 |
                                                                                                                      | Schema check | `SHOW COLUMNS` | ✅ 14 columns |
                                                                                                                      | Aliased, sorted SELECT | Top row by population | ✅ China, 1,277,558,000 |
                                                                                                                      | `WHERE ... AND ...` range filter | 50M < Population < 100M | ✅ 14 rows |
                                                                                                                      | Challenge query | Southern Europe, Population > 50M | ✅ Italy, 57,680,000 — matches answer key |
                                                                                                                      
                                                                                                                      ## Key Takeaways
                                                                                                                      
                                                                                                                      - **`SELECT` with `AS` turns raw column names into presentation-ready labels** without touching the underlying schema — useful any time a query's output is meant for a report or dashboard rather than another query.
                                                                                                                      - **`ORDER BY ... DESC` plus a `LIMIT` is the fastest way to sanity-check "biggest N" questions** (here, the 10 most populous countries) before writing a more targeted filter.
                                                                                                                      - **A `WHERE` clause with `AND` narrows on multiple independent conditions at once** — the 50M–100M population band and the Southern-Europe-plus-population challenge both needed two conditions to be true simultaneously, not two separate queries unioned together.
                                                                                                                      - **Checking a schema with `SHOW COLUMNS` before writing filters avoids guessing column names** — knowing `Region` and `Population` were plain `char`/`int` columns (not nested or derived) made the `WHERE Region = "Southern Europe"` filter a direct equality check.
                                                                                                                      - **Matching a lab's own hidden answer key is a good forcing function for correctness** — running the challenge query and getting the exact single row (Italy) the lab expected confirmed the filter logic rather than just trusting that the query "looked right."
                                                                                                                      
                                                                                                                      ## Lab Cleanup
                                                                                                                      
                                                                                                                      Ended the lab session via the AWS Skill Builder console, which tears down all lab-provisioned resources (the Command Host EC2 instance and the MariaDB instance) automatically.
                                                                                                                      
                                                                                                                      ---
                                                                                                                      *Completed as part of ongoing hands-on AWS cloud/database practice.*
                                                                                                                      
