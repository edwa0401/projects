# AWS Hands-On Lab: Insert, Update, and Delete Data in a Database

**Platform:** AWS Skill Builder (Vocareum)
**Date completed:** November 9, 2026
**Duration:** ~45 minutes
**Region:** US West (Oregon) — us-west-2

## Overview

**Scenario:** The database operations team created a relational database called `world` containing three tables: `city`, `country`, and `countrylanguage`. The task was to validate the configuration of the database by running `INSERT`, `UPDATE`, and `DELETE` statements against the `country` table, then confirm an SQL backup file could repopulate the schema from scratch.

This lab is a hands-on run through core SQL data manipulation language (DML) — inserting rows, updating them with and without a `WHERE` clause, deleting them, and restoring a table from a `.sql` backup file — against a pre-built MariaDB instance.

## Objectives

- Insert rows into a table
- Update rows in a table
- Delete rows from a table
- Import rows from a database backup file

## Architecture

```
EC2 "Command Host" (Session Manager, no SSH key)
     │  mysql client → MariaDB 10.5.29, logged in as root
     ▼
world database
 ├─ country          (Code, Name, Continent, Region, SurfaceArea, Population, GNP, etc.)
 ├─ city
 └─ countrylanguage
```

## Task 1: Connect to the Lab Environment

1. Opened a terminal session on the `Command Host` instance via **AWS Systems Manager → Session Manager** — no SSH key pair required.
2. Configured the shell and connected to the pre-installed MariaDB instance as `root`:
   ```
   sudo su
   cd /home/ec2-user/
   mysql -u root --password='re:St@rt!9'
   ```
   ```
   Welcome to the MariaDB monitor.
   Server version: 10.5.29-MariaDB
   ```
3. Confirmed the existing databases:
   ```sql
   SHOW DATABASES;
   ```
   Returned `information_schema`, `mysql`, `performance_schema`, and `world`.

**Result:** Connected and ready to run DML statements against `world.country`.

## Task 2: Insert Data into a Table

1. Verified the `country` table existed and was empty:
   ```sql
   SELECT * FROM world.country;
   ```
   → `Empty set`
2. Inserted two rows, matching the table's column order exactly:
   ```sql
   INSERT INTO world.country VALUES ('IRL','Ireland','Europe','British Islands',70273.00,1921,3775100,76.8,75921.00,73132.00,'Ireland/Éire','Republic',1447,'IE');

   INSERT INTO world.country VALUES ('AUS','Australia','Oceania','Australia and New Zealand',7741220.00,1901,18886000,79.8,351182.00,392911.00,'Australia','Constitutional Monarchy, Federation',135,'AU');
   ```
3. Verified both rows landed correctly:
   ```sql
   SELECT * FROM world.country WHERE Code IN ('IRL', 'AUS');
   ```

**Result:** 2 rows in set — Australia (Population 18,886,000) and Ireland (Population 3,775,100), matching the expected values.

## Task 3: Update Rows in a Table

1. Ran an `UPDATE` with no `WHERE` clause, which zeroed out `Population` for **every** row in the table (only 2 rows existed at this point):
   ```sql
   UPDATE world.country SET Population = 0;
   ```
   → `Rows matched: 2  Changed: 2`
2. Verified both rows now showed `Population = 0`.
3. Updated two columns at once:
   ```sql
   UPDATE world.country SET Population = 100, SurfaceArea = 100;
   ```
   → `Rows matched: 2  Changed: 2`
4. Verified `Population` and `SurfaceArea` were both `100` for Australia and Ireland.

**Result:** Confirmed that an `UPDATE` without a `WHERE` clause applies to every row in the table — a useful (and risky) behavior to understand before writing targeted updates.

## Task 4: Delete Rows from a Table

1. Disabled foreign key checks and deleted every row from `country`:
   ```sql
   SET FOREIGN_KEY_CHECKS = 0;
   DELETE FROM world.country;
   ```
   → `Query OK, 2 rows affected`
2. Verified the table was empty:
   ```sql
   SELECT * FROM world.country;
   ```
   → `Empty set`

**Result:** Confirmed `DELETE` without a `WHERE` clause removes all rows, same risk profile as the unscoped `UPDATE` in Task 3.

## Task 5: Import Data Using an SQL File

1. Exited the MySQL client (`QUIT;`) and confirmed the lab's pre-staged backup file was present:
   ```
   ls /home/ec2-user/world.sql
   ```
2. Loaded the backup directly from the shell, piping the `.sql` file into the client:
   ```
   mysql -u root --password='re:St@rt!9' < /home/ec2-user/world.sql
   ```
3. Reconnected and confirmed the schema was restored:
   ```sql
   USE world;
   SHOW TABLES;
   ```
   → `city`, `country`, `countrylanguage`
4. Verified rows loaded into all three tables:
   ```sql
   SELECT COUNT(*) FROM country;         -- 237
   SELECT COUNT(*) FROM city;            -- 4,079
   SELECT COUNT(*) FROM countrylanguage; -- 984
   ```

**Result:** The backup file repopulated `country` with 237 rows (versus the 2 rows manually inserted in Task 2) and added the full `city` (4,079 rows) and `countrylanguage` (984 rows) tables — confirming a `.sql` dump is the practical way to bulk-load or restore data instead of writing out individual `INSERT` statements.

## Verification Summary

| Step | Expected Result | Observed |
|---|---|---|
| Connect to MariaDB | Login succeeds as root | ✅ MariaDB 10.5.29 |
| `world` database present | Listed by SHOW DATABASES | ✅ Present |
| Insert 2 rows | IRL and AUS present in `country` | ✅ 2 rows, values matched |
| Update Population = 0 | All rows affected | ✅ 2/2 rows changed |
| Update Population/SurfaceArea = 100 | Both columns updated | ✅ 2/2 rows changed |
| Delete all rows | `country` table empty | ✅ Empty set |
| Import `world.sql` | 3 tables restored with data | ✅ city / country / countrylanguage present |
| Row counts after import | Full dataset loaded | ✅ 237 / 4,079 / 984 rows |

## Key Takeaways

- **`UPDATE` and `DELETE` without a `WHERE` clause affect every row in the table** — the lab deliberately demonstrates this risk before introducing scoped conditions, which is a good habit to carry into production work: always run a `SELECT` with the intended `WHERE` clause first to confirm the target row set.
- **Column order in an `INSERT ... VALUES` statement must match the table schema exactly** — there's no column-name safety net unless you explicitly list column names in the `INSERT` statement.
- **A `.sql` backup file piped into the `mysql` client (`mysql ... < file.sql`) is the standard, fast way to bulk-load or restore a database** — far more practical than hand-writing hundreds of `INSERT` statements, and it's the same mechanism used for real-world backup/restore workflows.
- **`SET FOREIGN_KEY_CHECKS = 0` before a `DELETE`** is a common pattern when a table has foreign key relationships that would otherwise block the delete — worth remembering as a troubleshooting step for constraint errors.

## Lab Cleanup

Ended the lab session via the AWS Skill Builder console, which tears down all lab-provisioned resources (EC2 Command Host and the MariaDB instance) automatically.

---
*Completed as part of ongoing hands-on AWS cloud/database practice.*
