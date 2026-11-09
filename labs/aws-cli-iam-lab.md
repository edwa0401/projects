# AWS Hands-On Lab: Installing and Configuring the AWS CLI

**Platform:** AWS Skill Builder (Vocareum)
**Date completed:** November 8, 2026
**Duration:** ~45 minutes
**Region:** US West (Oregon) — us-west-2

## Overview

This lab walks through installing and configuring the AWS Command Line Interface (AWS CLI) on an EC2 instance that doesn't ship with it pre-installed, then uses the CLI to interact with AWS Identity and Access Management (IAM). The scenario: connect to the instance over SSH, install the AWS CLI from scratch, configure it with an IAM user's access keys, and use it to inspect IAM users and policies — first through the AWS Management Console, then by running the equivalent commands from the CLI.

## Objectives

- Install and configure the AWS CLI.
- Connect the AWS CLI to an AWS account.
- Access IAM by using the AWS CLI.

## Architecture

```
                 Secure Shell (SSH)
   User  ──────────────────────────────▶  EC2 instance
                                            ┌─────────────────────────┐
                                            │        VPC               │
                                            │  ┌─────────────────────┐ │
                                            │  │   AWS CLI (CLI)     │ │
                                            │  │         │           │ │
                                            │  │         ▼           │ │
                                            │  │  IAM (awsstudent)   │ │
                                            │  └─────────────────────┘ │
                                            └─────────────────────────┘
                                                     AWS Cloud
```

## Task 1: Connect to the EC2 instance by using SSH

Downloaded `labsuser.pem` from the lab's Details panel, set it to read-only, and connected over SSH:

```
chmod 400 labsuser.pem
ssh -i labsuser.pem ec2-user@34.220.131.26
```

**Finding:** the lab instructions describe this as a "Red Hat EC2 instance," but the actual instance's MOTD banner identified it as **Amazon Linux 2**, not Red Hat. This matters because the lab's premise is that the instance doesn't come with the AWS CLI pre-installed ("Some instance types, such as Amazon Linux, do come pre-installed with the AWS CLI") — this particular Amazon Linux 2 instance had been deliberately stripped of it to force the manual install in Task 2.

**Result:** SSH connection established successfully as `ec2-user@ip-10-200-0-250`.

## Task 2: Install the AWS CLI

Downloaded, unzipped, and installed the AWS CLI v2 from the terminal:

```
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -u awscliv2.zip
sudo ./aws/install
aws --version
```

Output confirmed a working install:

```
aws-cli/2.3.96 Python/3.14.8 Linux/4.14.355-287.758.amzn2.x86_64 exe/x86_64.amzn2
```

**Result:** AWS CLI v2 installed and verified working on the instance.

## Task 3: Observe IAM configuration details in the AWS Management Console

In the AWS Management Console, navigated to IAM → Users → `awsstudent` → Permissions tab, and opened the `lab_policy` customer-managed policy in JSON view. The policy is a broad allow list scoped mostly to read/list/describe-style actions across EC2, CloudWatch, CloudFormation, IAM, KMS, SSM, SNS, and tagging, with a second statement explicitly denying a handful of EC2 actions (reserved instances, Spot, FPGA, capacity reservations, VPN gateway creation, fast snapshot restore, and VPC endpoint connection acceptance).

On the Security credentials tab, located the `awsstudent` IAM user's access key ID (`AKIAR6UIODXXU3O3JJV5`), matching the key provided in the lab's Details panel.

**Result:** Confirmed the IAM user and policy the CLI would later be configured to use.

## Task 4: Configure the AWS CLI to connect to the AWS account

```
aws configure
```

Supplied the access key ID, secret access key, region (`us-west-2`), and output format (`json`) from the lab's Details panel.

**Result:** AWS CLI configured and connected to the account (account ID `134503865839`).

## Task 5: Observe IAM configuration details by using the AWS CLI

```
aws iam list-users
```

Returned:

```json
{
    "Users": [
        {
            "Path": "/",
            "UserName": "awsstudent",
            "UserId": "AIDAR6UIODXXSXEQ6GJR4X",
            "Arn": "arn:aws:iam::134503865839:user/awsstudent",
            "CreateDate": "2026-11-09T03:05:34+00:00"
        }
    ]
}
```

**Result:** Confirmed the AWS CLI could reach IAM and retrieve the same user seen in the console in Task 3.

## Activity 1 challenge: Download the lab_policy document via the CLI

Used the AWS CLI (not the console) to retrieve the same `lab_policy` document viewed in Task 3, per the challenge instructions.

First, listed customer-managed policies to find the policy's ARN and current version:

```
aws iam list-policies --scope Local
```

```json
{
    "Policies": [
        {
            "PolicyName": "lab_policy",
            "PolicyId": "ANPAR6UIODXX5AWPQJNTI",
            "Arn": "arn:aws:iam::134503865839:policy/lab_policy",
            "Path": "/",
            "DefaultVersionId": "v1",
            "AttachmentCount": 1,
            "PermissionsBoundaryUsageCount": 0,
            "IsAttachable": true,
            "CreateDate": "2026-11-09T03:06:11+00:00",
            "UpdateDate": "2026-11-09T03:06:11+00:00"
        }
    ]
}
```

Then retrieved the actual JSON policy document using that ARN and version ID, saving it to a file:

```
aws iam get-policy-version --policy-arn arn:aws:iam::134503865839:policy/lab_policy --version-id v1 > lab_policy.json
cat lab_policy.json
```

This returned the full policy document — an `AllowAllActions` statement covering broad list/describe/get-style access across EC2, CloudFormation, CloudWatch, IAM, KMS, SSM, SNS, logs, and tagging, plus a `RestrictActions` statement explicitly denying Spot/Reserved Instance/FPGA/capacity-reservation/VPN-gateway-creation actions — matching what was seen in the console in Task 3.

**Result:** Successfully retrieved the `lab_policy` document entirely from the AWS CLI, without using the Management Console, completing the challenge.

## Summary

Installed the AWS CLI v2 on an Amazon Linux 2 instance (mislabeled "Red Hat" in the lab instructions) that had it deliberately omitted, connected it to the lab AWS account using an IAM user's access keys, and used it to retrieve IAM user and policy information — first cross-checking against the Management Console, then completing the Activity 1 challenge by pulling the same `lab_policy` JSON document purely through `aws iam list-policies` and `aws iam get-policy-version`. Key takeaway: the AWS CLI and the Management Console are two interchangeable paths to the same IAM data — the CLI just needs an access key/secret pair where the console relies on a signed-in session. The lab was ended afterward to tear down resources.
