# AWS Hands-On Lab: Creating a Website on S3

**Platform:** AWS Skill Builder (Vocareum)
**Date completed:** November 9, 2026
**Duration:** ~45 minutes
**Region:** US West (Oregon) — us-west-2

## Overview

This lab practices using the AWS CLI from an EC2 instance to stand up a static website on Amazon S3. The scenario is a fictional "Café & Bakery" business that needs its site hosted cheaply and reliably. The work covers creating an S3 bucket, creating a least-privilege-style IAM user scoped to S3, enabling static website hosting, uploading the site content with public-read access, and writing a reusable deployment script so future content changes are a one-line redeploy instead of a manual re-upload.

## Objectives

- Run AWS CLI commands that use IAM and Amazon S3 services.
- Deploy a static website to an S3 bucket.
- Create a script that uses the AWS CLI to copy files in a local directory to Amazon S3.

## Architecture

```
                 AWS Management Console        AWS CLI (from EC2 via SSM)
                           |                              |
                           +--------------+---------------+
                                          |
                                   AWS Cloud (us-west-2)
                                          |
                                 S3 bucket: redwards519
                                 - static website hosting enabled
                                 - index document: index.html
                                 - IAM user awsS3user: AmazonS3FullAccess
                                          |
        Client  --- http(s) ---> http://redwards519.s3-website-us-west-2.amazonaws.com
```

## Task 1: Connect to an Amazon Linux EC2 instance using SSM

Connected to the lab's EC2 instance through AWS Systems Manager Session Manager using the `InstanceSessionUrl` from the lab's Cloud Access panel, then switched to the `ec2-user` context:

```bash
sudo su -l ec2-user
pwd
```

**Result:** Session opened at `/home/ec2-user`.

## Task 2: Configure the AWS CLI

Ran `aws configure` and supplied the lab's temporary access key, secret key, region (`us-west-2`), and output format (`json`). Amazon Linux ships with the AWS CLI preinstalled, so no install step was needed.

**Result:** CLI configured; verified later with a successful `aws sts get-caller-identity` call.

## Task 3: Create an S3 bucket using the AWS CLI

```bash
aws s3api create-bucket --bucket redwards519 --region us-west-2 \
  --create-bucket-configuration LocationConstraint=us-west-2
```

```json
{
    "Location": "http://redwards519.s3.amazonaws.com/"
}
```

**Result:** Bucket `redwards519` created in `us-west-2`.

## Task 4: Create a new IAM user that has full access to Amazon S3

```bash
aws iam create-user --user-name awsS3user
aws iam create-login-profile --user-name awsS3user --password <redacted>
aws iam list-policies --query "Policies[?contains(PolicyName,'S3')]"
aws iam attach-user-policy \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess \
  --user-name awsS3user
```

`list-policies` surfaced the AWS-managed `AmazonS3FullAccess` policy (`arn:aws:iam::aws:policy/AmazonS3FullAccess`), which was attached to the new `awsS3user` user so it can manage S3 without broader account access.

**Result:** IAM user `awsS3user` created with a console login profile and `AmazonS3FullAccess` attached.

## Task 5: Adjust S3 bucket permissions

On the bucket's **Permissions** tab in the AWS Management Console:

- **Block public access (bucket settings):** edited and turned **off** "Block all public access" (confirmed with the "confirm" acknowledgment prompt).
- **Object Ownership:** switched from "Bucket owner enforced" (ACLs disabled) to **ACLs enabled**, acknowledging that ACLs would be restored.

![Block public access off, ACLs enabled](screenshots/04-bucket-permissions.jpg)

**Result:** The bucket can now accept public-read ACLs on uploaded objects, which the upload step depends on.

## Task 6: Extract the files needed for this lab

```bash
cd ~/sysops-activity-files
tar xvzf static-website-v2.tar.gz
cd static-website
ls
```

![Extracted site files: index.html, css/, images/](screenshots/02-extract-files.jpg)

**Result:** Confirmed `index.html` plus `css/` and `images/` directories for the Café & Bakery site.

## Task 7: Upload files to Amazon S3 using the AWS CLI

```bash
aws s3 website s3://redwards519/ --index-document index.html
aws s3 cp /home/ec2-user/sysops-activity-files/static-website/ s3://redwards519/ \
  --recursive --acl public-read
aws s3 ls redwards519
```

![Static website hosting enabled, files uploaded with public-read ACL](screenshots/03-upload-to-s3.jpg)

Loaded the site to confirm it rendered (via the bucket's HTTPS object URL — see Finding below):

![Café & Bakery site live on S3, original aquamarine/orange colors](screenshots/05-site-live-before.jpg)

**Result:** All files (`index.html`, `css/styles.css`, 7 images) uploaded and publicly readable; site rendered correctly.

**Finding:** Chrome enforces HTTPS on the `*.amazonaws.com` domain (HSTS), which breaks the plain-HTTP-only S3 **website** endpoint (`redwards519.s3-website-us-west-2.amazonaws.com`) with a cert error in-browser. Verified the deployed content instead via the bucket's HTTPS object URL (`https://redwards519.s3.amazonaws.com/index.html`), which serves the same `index.html` and confirms the upload worked; the website endpoint itself was still configured correctly via `aws s3 website`.

## Task 8: Create a batch file to make updating the website repeatable

Instead of driving `vi` interactively, used a heredoc to write the same script content, then made it executable:

```bash
cd ~
cat > update-website.sh << 'EOF'
#!/bin/bash
aws s3 cp /home/ec2-user/sysops-activity-files/static-website/ s3://redwards519/ --recursive --acl public-read
EOF
chmod +x update-website.sh
```

To prove the redeploy script works, edited `index.html`'s table background colors (first `bgcolor="aquamarine"` → `gainsboro`, `bgcolor="orange"` → `cornsilk`, second `bgcolor="aquamarine"` → `gainsboro`) with a targeted `sed` instead of interactive `vi`:

```bash
sed -i '31s/bgcolor="aquamarine"/bgcolor="gainsboro"/; \
        39s/bgcolor="orange"/bgcolor="cornsilk"/; \
        47s/bgcolor="aquamarine"/bgcolor="gainsboro"/' \
  ~/sysops-activity-files/static-website/index.html
./update-website.sh
```

![update-website.sh re-uploading all files after the color edit](screenshots/06-update-script-run.jpg)

![Café & Bakery site live with new gainsboro/cornsilk colors](screenshots/07-site-live-after.jpg)

**Result:** Running `./update-website.sh` re-uploaded all files in one command, and the live site reflected the new colors immediately — the repeatable deploy path works.

## Summary

Built a working static website on S3 end to end: bucket creation, an IAM user scoped to S3 only, public-read bucket permissions, a CLI-based deploy of the Café & Bakery site, and a one-command redeploy script proven by actually changing the site and re-running it. The only real snag was Chrome's HSTS rule blocking the plain-HTTP S3 website endpoint directly in-browser — worked around by verifying through the bucket's HTTPS object URL instead, since that confirms the same uploaded content.

Per Ryan's request, this lab environment was **left running** (not ended) after documentation so it can be reviewed further.
