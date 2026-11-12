import { useAppConfig } from "../components/AppShell";

const MERMAID = `flowchart LR
  staff([Staff browser]) -->|HTTPS| cf[CloudFront + private S3<br/>React app]
  staff -->|Hosted UI sign-in, PKCE| cognito[Amazon Cognito<br/>user pool + staff group]
  staff -->|Bearer access token| apigw[API Gateway HTTP API<br/>JWT authorizer, CORS]
  apigw --> lambda[Lambda Python 3.12<br/>validation, workflow, guardrails]
  lambda -->|Converse API| bedrock[Amazon Bedrock<br/>configurable model]
  lambda --> ddb[(DynamoDB<br/>inquiries, audit,<br/>achievements, idempotency)]
  lambda --> cw[CloudWatch Logs<br/>no message bodies]`;

const STEPS = [
  ["Customer inquiry is entered", "Staff paste an email, text, or phone note. The API validates it and saves it to DynamoDB before any AI call."],
  ["AI analysis", "Lambda calls Bedrock through the Converse API with a single side-effect-free tool. The response is validated against a JSON schema."],
  ["Guardrails", "Ungrounded extracted values are removed, prompt-injection signals force manual review, and draft commitments are flagged."],
  ["Staff review", "Staff correct category, priority, assignment, and the draft. Every change is written with an audit event in one transaction."],
  ["Approval", "Requires a completed verification checklist and a draft with no price, availability, or booking commitments. Nothing is sent automatically."],
  ["Resolution", "Staff copy the approved response into their own tools and mark the inquiry resolved. Metrics update from the records."],
];

export function BuildGuidePage() {
  const config = useAppConfig();
  return (
    <div className="guide">
      <h1>AWS build guide</h1>
      <p className="muted">
        How LeadRescue runs on AWS. The repository README has the full commands. Nothing on this page deploys anything; deployment creates billable
        resources and should be run deliberately.
      </p>
      <p>
        Current environment: <strong>{config?.mode === "live" ? "Live AI mode (Amazon Bedrock)" : "Demo mode (local, no AWS resources)"}</strong>
      </p>

      <section className="card" aria-labelledby="arch-title">
        <h2 id="arch-title">Architecture</h2>
        <div className="arch" role="img" aria-label="Architecture: staff browser uses CloudFront for the app, Cognito for sign-in, and API Gateway with a JWT authorizer. API Gateway invokes a Python Lambda that calls Amazon Bedrock and stores data in DynamoDB, logging to CloudWatch.">
          <div className="arch-col">
            <div className="arch-box user">Staff browser</div>
          </div>
          <div className="arch-col">
            <div className="arch-box">CloudFront + S3<span>React app</span></div>
            <div className="arch-box">Amazon Cognito<span>Hosted UI, staff group</span></div>
            <div className="arch-box">API Gateway<span>HTTP API, JWT authorizer</span></div>
          </div>
          <div className="arch-col">
            <div className="arch-box core">Lambda<span>Python 3.12 · validation, workflow, guardrails</span></div>
          </div>
          <div className="arch-col">
            <div className="arch-box">Amazon Bedrock<span>Converse API</span></div>
            <div className="arch-box">DynamoDB<span>4 on-demand tables</span></div>
            <div className="arch-box">CloudWatch<span>Structured logs</span></div>
          </div>
        </div>
        <details>
          <summary>Mermaid source</summary>
          <pre className="code">{MERMAID}</pre>
        </details>
      </section>

      <section className="card" aria-labelledby="flow-title">
        <h2 id="flow-title">Request lifecycle</h2>
        <ol className="steps">
          {STEPS.map(([t, d]) => (
            <li key={t}>
              <strong>{t}.</strong> {d}
            </li>
          ))}
        </ol>
      </section>

      <section className="card" aria-labelledby="deploy-title">
        <h2 id="deploy-title">Deploy (AWS SAM)</h2>
        <ol className="steps">
          <li>
            In the Bedrock console for your Region, confirm the model you plan to use is available to your account and supports the Converse API with tool
            use. Note its model ID or inference profile ID.
          </li>
          <li>
            Install the AWS CLI and SAM CLI and sign in with an account that can create IAM roles. Run <code>sam build</code> from the <code>infra</code>{" "}
            folder.
          </li>
          <li>
            Run <code>sam deploy --guided</code> and provide <code>BedrockModelId</code>, <code>CognitoDomainPrefix</code>, and{" "}
            <code>AllowedOrigin</code> (your CloudFront URL, or update after the first deploy).
          </li>
          <li>Build the frontend with the stack outputs as Vite variables, then upload <code>frontend/dist</code> to the site bucket.</li>
          <li>
            Create staff users in the Cognito user pool and add them to the <code>staff</code> group.
          </li>
          <li>Run the live evaluation and review the results before trusting any AI output.</li>
        </ol>
      </section>

      <section className="card" aria-labelledby="config-title">
        <h2 id="config-title">Configuration</h2>
        <table className="data-table">
          <caption className="sr-only">Configuration settings</caption>
          <thead>
            <tr>
              <th scope="col">Setting</th>
              <th scope="col">Where</th>
              <th scope="col">Purpose</th>
            </tr>
          </thead>
          <tbody>
            <tr><td><code>BedrockModelId</code></td><td>SAM parameter</td><td>Model or inference profile ID. Required for live AI. No default model access is assumed.</td></tr>
            <tr><td><code>BedrockToolChoice</code></td><td>SAM parameter</td><td><code>auto</code> (default) or <code>tool</code>. Some newer models reject forced tool choice.</td></tr>
            <tr><td><code>AllowedOrigin</code></td><td>SAM parameter</td><td>CORS origin for the API and Cognito callback base URL.</td></tr>
            <tr><td><code>CognitoDomainPrefix</code></td><td>SAM parameter</td><td>Hosted UI domain prefix (must be globally unique).</td></tr>
            <tr><td><code>VITE_AUTH_MODE</code>, <code>VITE_API_BASE_URL</code>, <code>VITE_COGNITO_*</code></td><td>Frontend build</td><td>Switch the app from demo sign-in to Cognito and point it at the API.</td></tr>
            <tr><td><code>AI_PROVIDER</code>, <code>STORE</code></td><td>Lambda environment</td><td>Set by the template to <code>bedrock</code> and <code>dynamodb</code>.</td></tr>
          </tbody>
        </table>
        <p className="small muted">No secrets are stored in code or configuration. Lambda uses its IAM role; the browser uses short-lived Cognito tokens.</p>
      </section>

      <section className="card" aria-labelledby="cleanup-title">
        <h2 id="cleanup-title">Cleanup</h2>
        <ol className="steps">
          <li>Empty the site bucket: <code>aws s3 rm s3://BUCKET --recursive</code>.</li>
          <li>Delete the stack: <code>sam delete --stack-name leadrescue</code>. DynamoDB tables and the user pool are removed with it.</li>
          <li>Check CloudWatch log groups and delete any that remain if you do not need them.</li>
        </ol>
      </section>

      <section className="card" aria-labelledby="limits-title">
        <h2 id="limits-title">Current limitations and next steps</h2>
        <ul>
          <li>Live Bedrock analysis is implemented and unit-tested with a stubbed client, but has not been run against a real model in this build.</li>
          <li>Outbound delivery (email/SMS) is out of scope: staff copy approved responses manually.</li>
          <li>The queue lists up to 500 recent records per workspace with in-memory filtering; add pagination and server-side filters for larger volumes.</li>
          <li>Single staff role. Next: manager role for reassigning, reopening resolved inquiries, and exporting audit history.</li>
          <li>The demo analyzer is rule-based and misses targets on the evaluation set; it exists only to run without AWS.</li>
          <li>Next steps: Step Functions for asynchronous analysis and retries, SES drafts with approval, and AWS WAF in front of the API.</li>
        </ul>
      </section>
    </div>
  );
}
