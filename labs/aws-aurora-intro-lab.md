# AWS Hands-On Lab: Introduction to Amazon Aurora

**Platform:** AWS Skill Builder (Vocareum)
**Date completed:** November 7, 2026
**Duration:** ~40 minutes
**Region:** US West (Oregon) — us-west-2

## Overview

This lab is a first hands-on pass at Amazon Aurora: stand up an Aurora MySQL-compatible cluster, connect to a pre-provisioned EC2 "command host" over Session Manager, install a MySQL-compatible client, and run real SQL against the cluster — creating a table, loading rows, and querying them.

**Scenario:** A pre-created EC2 instance (`Command Host`) needs to reach a new Aurora cluster (`aurora`) that hosts a `world` database. The task is to provision the cluster, wire up connectivity through an existing VPC/security group, and prove the connection works end to end with a real query.

## Objectives

- Create an Aurora instance
- Connect to a pre-created Amazon EC2 instance
- Configure the Amazon EC2 instance to connect to Aurora
- Query the Aurora instance

## Architecture

```
EC2 "Command Host" (LabVPC)
     │  mysql client (MariaDB client package)
     ▼
Aurora MySQL cluster "aurora"  (writer endpoint, port 3306)
     │  DBSecurityGroup (no default SG, no public access)
     ▼
"world" database → country table (5 rows loaded)
```

## Task 1: Create an Aurora Instance

Created the cluster from RDS → Create database → **Full configuration**:

- **Engine:** Aurora (MySQL Compatible)
- **Templates:** Dev/Test
- **Cluster scalability:** Provisioned → Burstable classes (t) → `db.t3.medium`
- **Engine version:** selecting `db.t3.medium` pulled in Aurora MySQL 3.10.3 (compatible with MySQL 8.0.42) — the console's default 5.7-compatible (2.x) versions aren't usable on that instance class, so this was the effective "default for major version 8.0" in this environment
- **DB cluster identifier:** `aurora`
- **Master username / password:** `admin` / `admin123` (self-managed credentials, not Secrets Manager)
- **Multi-AZ:** Don't create an Aurora Replica
- **Connectivity:** VPC `LabVPC`, DB subnet group `dbsubnetgroup`, Public access **No**, VPC security group set to `DBSecurityGroup` only (removed the `default` SG)
- **Initial database name:** `world`
- **Monitoring:** Enhanced Monitoring off, Database Insights per-query/counter metrics off
- **Maintenance:** Auto minor version upgrade off

**Result:** Cluster `aurora` with writer instance `aurora-instance-1` reached **Available** status, writer endpoint `aurora.cluster-cqwdyy5blfis.us-west-2.rds.amazonaws.com`.

## Task 2: Connect to the Amazon EC2 Instance

1. In EC2 → Instances, opened the pre-created `Command Host` instance (already `Running`, 3/3 status checks passed).
2. Chose **Connect** → **SSM Session Manager** (shown as "Maximum security / IAM authentication," SSM agent already online and connected) → **Connect**.

**Result:** A browser-based terminal session opened on `Command Host` with no SSH key required.

## Task 3: Configure the EC2 Instance to Connect to Aurora

1. Installed the MariaDB client (provides the `mysql` CLI):
   ```bash
   sudo yum install mariadb -y
   ```
2. Copied the Aurora writer endpoint from the RDS console and connected:
   ```bash
   mysql -u admin --password='admin123' -h aurora.cluster-cqwdyy5blfis.us-west-2.rds.amazonaws.com
   ```
3. Confirmed the connection banner:
   ```
   Welcome to the MariaDB monitor.
   Server version: 8.0.42 6252a59a
   ```

**Result:** `Command Host` is talking to the Aurora cluster over the `DBSecurityGroup` rule, authenticated as `admin`.

## Task 4: Create a Table and Insert and Query Records

1. Listed databases and switched into the pre-created one:
   ```sql
   SHOW DATABASES;      -- information_schema, mysql, performance_schema, sys, world
   USE world;
   ```
2. Created the `country` table (14 columns: `Code`, `Name`, `Continent`, `Region`, `SurfaceArea`, `IndepYear`, `Population`, `LifeExpectancy`, `GNP`, `GNPOld`, `LocalName`, `GovernmentForm`, `Capital`, `Code2`; primary key `Code`).
3. Inserted 5 rows: Gabon, Ireland, Thailand, Costa Rica, Australia.
4. Ran the lab's verification query:
   ```sql
   SELECT * FROM country WHERE GNP > 35000 and Population > 10000000;
   ```
   Returned exactly the two expected rows — **Australia** and **Thailand**.

**Result:** Table created, data loaded, and query returned the documented expected output.

## Verification Summary

| Step | Expected Result | Observed |
|---|---|---|
| Aurora cluster created | Status = Available | ✅ `aurora` / `aurora-instance-1` Available |
| EC2 → Aurora connectivity | mysql client connects | ✅ Connected, server version 8.0.42 |
| `world` database present | Listed by SHOW DATABASES | ✅ Present |
| `country` table created | Query OK, 0 rows affected | ✅ Created (7 warnings, expected) |
| 5 rows inserted | Query OK, 1 row affected ×5 | ✅ All 5 inserts succeeded |
| Verification query | 2 rows: Australia, Thailand | ✅ Exact match |

## Key Takeaways

- **Instance class can silently gate engine version.** Picking `db.t3.medium` (vs. the default `db.t3.small`) flipped the available engine version list from Aurora MySQL 2.x (5.7-compatible, past standard support) to 3.x (8.0-compatible) — worth checking instance class *before* assuming the engine version dropdown is final.
- **Aurora MySQL 2.x triggers RDS Extended Support charges.** The console blocked cluster creation on a 2.x engine version unless "Enable RDS Extended Support" was checked, since that major version is past its standard-support end date (Oct 31, 2024). Moving to the 3.x/8.0-compatible engine avoided that extra cost entirely.
- **Session Manager keeps the lab key-free.** Connecting to `Command Host` needed no SSH key pair — IAM-based Session Manager access was already wired up by the lab's CloudFormation setup.
- **Security groups are the real gatekeeper, not public access.** With Public access set to No and only `DBSecurityGroup` attached (default SG removed), connectivity still worked cleanly from inside the VPC — the lab's dedicated security group did the actual work.
- **MariaDB client == MySQL protocol compatibility.** `yum install mariadb` is enough to get a working `mysql` CLI against an Aurora MySQL-compatible cluster; no engine-specific client needed.

## Lab Cleanup

Ended the lab session via the AWS Skill Builder console (**End Lab** → confirmed), which tears down all lab-provisioned resources (Aurora cluster/instance, EC2 command host, VPC/security groups) automatically.

---
*Completed as part of ongoing hands-on AWS cloud/database practice.*
