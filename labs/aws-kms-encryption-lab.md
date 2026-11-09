# AWS Hands-On Lab: Data Protection Using Encryption

**Platform:** AWS Skill Builder (Vocareum)
**Date completed:** November 8, 2026
**Duration:** ~40 minutes
**Region:** US West (Oregon) — us-west-2

## Overview

This lab builds a basic encryption/decryption pipeline using AWS Key Management Service (KMS) and the AWS Encryption CLI. The task: create a symmetric KMS key, connect to a pre-provisioned EC2 "File Server" over Session Manager, install the AWS Encryption CLI, then encrypt a plaintext file into unreadable ciphertext and decrypt it back to its original contents — proving the full encrypt/decrypt round trip with a real KMS-backed key.

**Scenario:** A pre-created EC2 instance (`File Server`) needs an AWS KMS key and the AWS Encryption CLI to protect sensitive text files at rest. The task is to provision the key, configure the instance to use it, and verify that data encrypted with the key can only be read after a successful decrypt.

## Objectives

- Create an AWS KMS encryption key
- Install the AWS Encryption CLI
- Encrypt plaintext
- Decrypt ciphertext

## Architecture

```
AWS KMS                          EC2 "File Server" (Session Manager, no SSH key)
┌─────────────────────┐          ┌──────────────────────────────────┐
│ Symmetric key        │          │ ~/.aws/credentials (temp session) │
│ alias: MyKMSKey       │◀────────│ aws-encryption-cli (pip3)         │
│ Key admins/users:     │  KMS    │                                    │
│   voclabs role        │  API    │ secret1.txt  →  encrypt  →         │
└─────────────────────┘  calls   │   output/secret1.txt.encrypted    │
                                  │   → decrypt →                      │
                                  │   secret1.txt.encrypted.decrypted │
                                  └──────────────────────────────────┘
```

## Task 1: Create an AWS KMS Key

1. In the console, searched **KMS** and opened **Key Management Service** → **Customer managed keys** → **Create key**.
2. **Key type:** Symmetric. **Key usage:** Encrypt and decrypt (both pre-selected defaults).
3. **Add labels:**
   - **Alias:** `MyKMSKey`
   - **Description:** `Key used to encrypt and decrypt data files.`
4. **Key administrators:** searched for and selected the `voclabs` IAM role (the role pre-created for this lab).
5. **Key usage permissions:** searched for and selected `voclabs` again as a key user.
6. Reviewed the generated key policy (two statements: root account full access, and `voclabs` granted both administration and usage) and chose **Finish**.

**Result:** Key created with alias `MyKMSKey`, Key ID `056e6343-76eb-461a-9c53-d63818fc6263`, ARN `arn:aws:kms:us-west-2:557093591555:key/056e6343-76eb-461a-9c53-d63818fc6263`. Copied the ARN for use in later tasks.

## Task 2: Configure the File Server Instance

1. In EC2 → Instances, selected the pre-created **File Server** instance (Running, 2/2 status checks passed) → **Connect** → **SSM Session Manager** tab (shown as "Maximum security / IAM authentication," SSM agent online) → **Connect**.
2. In the Session Manager terminal, ran `cd ~ && aws configure`, entering placeholder values (`1`/`1`) for the access key and secret key, `us-west-2` for region, and the default output format — these placeholders get overwritten with the lab's real temporary session credentials in the next step.
3. Back in Vocareum, opened **AWS Details** → **AWS CLI** → **Show**, copied the real temporary credentials block (`aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`), and wrote them into `~/.aws/credentials` on the File Server.
4. Installed the AWS Encryption CLI and set the PATH:
   ```
   pip3 install aws-encryption-sdk-cli
   export PATH=$PATH:/home/ssm-user/.local/bin
   ```

**Result:** AWS credentials configured on the instance, and the AWS Encryption CLI (`aws-encryption-cli`) installed and on PATH.

## Task 3: Encrypt and Decrypt Data

1. Created the test files and output directory, and saved the KMS key ARN to a variable:
   ```
   touch secret1.txt secret2.txt secret3.txt
   echo 'TOP SECRET 1!!!' > secret1.txt
   mkdir output
   keyArn=arn:aws:kms:us-west-2:557093591555:key/056e6343-76eb-461a-9c53-d63818fc6263
   ```
2. Ran the encrypt command:
   ```
   aws-encryption-cli --encrypt \
     --input secret1.txt \
     --wrapping-keys key=$keyArn \
     --metadata-output ~/metadata \
     --encryption-context purpose=test \
     --commitment-policy require-encrypt-require-decrypt \
     --output ~/output/
   ```
3. **Hit a real environment bug:** the lab's EC2 AMI runs Python 3.7, and `pip3 install aws-encryption-sdk-cli` pulled the latest release (4.3.0), which assumes Python 3.8+'s built-in `importlib.metadata` module. On Python 3.7 that module doesn't exist as a stdlib submodule, so the CLI failed immediately with `ModuleNotFoundError: No module named 'importlib.metadata'`.
   - **Fix:** pinned to an older, Python 3.7-compatible release: `pip3 install 'aws-encryption-sdk-cli<4.0' --force-reinstall`. That first pulled in `aws-encryption-sdk-cli` 3.1.0 but kept the newer `aws-encryption-sdk` 3.3.1 already on disk, producing a `VersionConflict` (3.1.0 requires `aws-encryption-sdk~=2.3`). Re-running the same install **without** `--no-deps` let pip resolve the full compatible set: `aws-encryption-sdk-cli` 3.1.0, `aws-encryption-sdk` 2.5.1, and `cryptography` 36.0.2.
4. Re-ran the encrypt command — succeeded (exit code `0`). Verified with `ls ~/output` → `secret1.txt.encrypted`, and confirmed the file contents were unreadable binary ciphertext.
5. Ran the decrypt command:
   ```
   aws-encryption-cli --decrypt \
     --input output/secret1.txt.encrypted \
     --wrapping-keys key=$keyArn \
     --commitment-policy require-encrypt-require-decrypt \
     --encryption-context purpose=test \
     --metadata-output /tmp/decrypt-metadata \
     --max-encrypted-data-keys 1 \
     --buffer \
     --output .
   ```
   (Pointed `--metadata-output` outside the `--output` directory — pointing it at the same directory as the decrypt output is rejected with `Metadata output file cannot be in the output directory`.)
6. Viewed the result: `cat secret1.txt.encrypted.decrypted` → `TOP SECRET 1!!!`, matching the original plaintext exactly.

**Result:** Full encrypt → decrypt round trip verified against a real KMS key: `secret1.txt` → unreadable ciphertext (`secret1.txt.encrypted`) → decrypted back to the original plaintext (`secret1.txt.encrypted.decrypted`).

## Summary

In this lab, created a symmetric AWS KMS key (`MyKMSKey`) scoped to the `voclabs` role, configured a File Server EC2 instance with temporary session credentials and the AWS Encryption CLI, and ran a full encrypt/decrypt cycle against the key. Along the way, diagnosed and fixed a real Python-version/package-version incompatibility (`aws-encryption-sdk-cli` 4.3.0 vs. Python 3.7) by pinning to a compatible dependency set — the kind of packaging issue that shows up constantly outside of tutorial-perfect environments.

