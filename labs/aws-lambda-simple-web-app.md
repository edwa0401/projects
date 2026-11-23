# AWS Hands-On Lab: Create a Simple Web App with AWS Lambda

**Platform:** AWS Lambda console, built-in tutorial ("Create a simple web app")
**Date completed:** November 22, 2026
**Duration:** ~10 minutes
**Region:** US East (N. Virginia) — us-east-1

## Overview

This guided console tutorial builds the smallest possible serverless web app: a single AWS Lambda function exposed through a **Lambda Function URL**. There is no API Gateway, no load balancer, and no server. An HTTPS request to the function URL invokes the function, which reads a bundled `index.html` file and returns it with a `text/html` content type, so the browser renders a server-side generated page.

**Scenario:** Stand up a public HTTP endpoint backed by Lambda using the console's Web Function blueprint, then invoke it from a browser to prove the request/response path works end to end.

## Objectives

- Create a Lambda Web Function from the sample (blueprint) code
- Expose it with a Function URL
- Choose an authentication type for the endpoint
- Invoke the function over HTTPS from a browser

## Architecture

```
Browser
   │  HTTPS GET
   ▼
Lambda Function URL  (https://<url-id>.lambda-url.us-east-1.on.aws/)
   │  Auth type: NONE   Invoke mode: BUFFERED   CORS: off
   ▼
Lambda function: salesAnalysisReportDataExtractor
   Runtime: Node.js (ES module)   Handler: index.handler
   ├── index.mjs   → reads index.html, returns { statusCode: 200,
   │                  headers: { Content-Type: text/html }, body }
   └── index.html  → "Hello from AWS Lambda!" page
```

## Task 1: Create the Web Function

1. **Step 1: Name your Web Function.** Named the function `salesAnalysisReportDataExtractor`.
2. **Step 2: Choose your code source and review the sample code.** Used the tutorial's sample code. The package contains two files:
   - `index.html`: the static page that gets rendered.
   - `index.mjs`: the handler. It loads `index.html` once at module init with `fs.readFileSync` (outside the handler, so warm invocations reuse it), then the async `handler` returns `statusCode: 200`, a `Content-Type: text/html` header, and the HTML as the body.

   ```javascript
   import * as fs from 'node:fs';

   const html = fs.readFileSync('index.html', { encoding: 'utf8' });

   export const handler = async () => {
       const response = {
           statusCode: 200,
           headers: { 'Content-Type': 'text/html' },
           body: html,
       };
       return response;
   };
   ```

3. **Step 3: Name your endpoint.** Created a Lambda Function URL for the function.
4. **Step 4: Choose the authentication type.** Selected **NONE**, making the URL public. The console flags this: "Your function URL is public. Anyone with the URL can access your function." The alternative, **AWS_IAM**, requires SigV4-signed requests and is the right choice for anything not meant for anonymous users.
5. **Step 5: Create the Web Function.** Created the function. Resulting Function URL configuration: Auth type **NONE**, Invoke mode **BUFFERED** (full response returned at once, as opposed to RESPONSE_STREAM), CORS **not enabled**. No triggers were needed; the Function URL is a built-in HTTPS endpoint, not a separate trigger.

**Result:** Lambda function deployed with a public HTTPS Function URL.

## Task 2: Invoke your Web Function

1. **Step 1: Open your endpoint URL.** Opened the Function URL in a new browser tab.
2. The browser received the HTML response and rendered the page headed **"Hello from AWS Lambda!"** with the subtitle "The blueprint function you created rendered this page", followed by next-step suggestions (read user input, store it in a serverless database, render content from the database).

**Result:** HTTPS GET to the Function URL returned 200 and rendered the server-side page, confirming the full browser → Function URL → Lambda → response path.

## Summary

Built a one-function serverless web app: Lambda returns HTML, and a Function URL gives it a public HTTPS endpoint without API Gateway. Key takeaways:

- **Function URLs** are the fastest way to put an HTTPS endpoint on a single Lambda function. API Gateway is still the better fit when you need routing across many functions, usage plans, API keys, request validation, or custom domains with WAF in front.
- **Auth type matters.** `NONE` is fine for a demo page; production endpoints should use `AWS_IAM` or put auth in the function, and enable CORS only for the origins that need it.
- **Init-phase work is reused.** Reading `index.html` outside the handler means the file is loaded once per execution environment, not on every request, a simple cold-start/warm-start optimization.
- **Lambda returns a structured response object** (`statusCode`, `headers`, `body`); the Function URL translates it into a real HTTP response.

**Finding worth noting:** the function name `salesAnalysisReportDataExtractor` was reused from the earlier "Working with AWS Lambda" sales-report lab. The Code tab still had a stale editor tab open for `salesAnalysisReportDataExtractor.py`, which showed "file not found" because the deployed package is now the Node.js `index.mjs` + `index.html` blueprint. Lesson: give each function a distinct name per project so a new deployment doesn't replace another workload's code.

The function and its public Function URL should be deleted after the lab (or the auth type switched to `AWS_IAM`) so the endpoint isn't left open.
