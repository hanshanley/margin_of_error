const finalFailures = new Set([
  "deployment_failed", "deployment_content_failed", "deployment_cancelled", "deployment_lost",
]);

export function validateRecovery({ artifact, run, jobs, comparison, expected, repositoryId }) {
  if (!Number.isSafeInteger(expected.artifactId) || !Number.isSafeInteger(expected.runId)
    || expected.artifactId <= 0 || expected.runId <= 0 || !/^[a-f0-9]{40}$/.test(expected.sourceCommit)
    || !/^sha256:[a-f0-9]{64}$/.test(expected.artifactDigest))
    throw new Error("Recovery requires pinned artifact, run, source commit and digest");
  if (artifact.id !== expected.artifactId || artifact.name !== "github-pages" || artifact.expired
    || artifact.digest !== expected.artifactDigest || artifact.workflow_run?.id !== expected.runId
    || artifact.workflow_run?.repository_id !== repositoryId
    || artifact.workflow_run?.head_repository_id !== repositoryId
    || artifact.workflow_run?.head_sha !== expected.sourceCommit)
    throw new Error("Original Pages artifact provenance or immutable digest differs");
  if (run.id !== expected.runId || run.head_sha !== expected.sourceCommit || run.head_branch !== "main"
    || !jobs.some(job => job.name === "build" && job.conclusion === "success")
    || !["ahead", "identical"].includes(comparison.status))
    throw new Error("Only a successful build from reviewed main ancestry can be redeployed");
}

export async function recoverPages({
  github, core, context, expected, now = Date.now,
  wait = ms => new Promise(resolve => setTimeout(resolve, ms)), timeout = 1_800_000,
}) {
  if (context.ref !== "refs/heads/main") throw new Error("Recovery runs only on main");
  const request = (route, values = {}) => github.request(route, {
    ...context.repo, headers: { "X-GitHub-Api-Version": "2026-03-10" }, ...values,
  });
  const [{ data: artifact }, { data: run }, { data: comparison }, jobs] = await Promise.all([
    request("GET /repos/{owner}/{repo}/actions/artifacts/{artifact_id}", { artifact_id: expected.artifactId }),
    request("GET /repos/{owner}/{repo}/actions/runs/{run_id}", { run_id: expected.runId }),
    request("GET /repos/{owner}/{repo}/compare/{basehead}", {
      basehead: `${expected.sourceCommit}...${context.sha}`,
    }),
    github.paginate("GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs", {
      ...context.repo, run_id: expected.runId, filter: "all", per_page: 100,
    }),
  ]);
  validateRecovery({ artifact, run, jobs, comparison, expected,
    repositoryId: context.payload.repository.id });
  const buildVersion = `${expected.sourceCommit}-${context.runId}-${context.runAttempt || 1}`;
  const idToken = await core.getIDToken();
  const { data: deployment } = await request("POST /repos/{owner}/{repo}/pages/deployments", {
    artifact_id: expected.artifactId, pages_build_version: buildVersion,
    oidc_token: idToken, environment: "github-pages",
  });
  if (!deployment.id) throw new Error("Pages did not return a deployment identity");
  const deadline = now() + timeout;
  while (now() < deadline) {
    const { data } = await request("GET /repos/{owner}/{repo}/pages/deployments/{deployment_id}", {
      deployment_id: deployment.id,
    });
    core.info(`Original artifact ${expected.artifactId}; Pages status: ${data.status || "pending"}`);
    if (data.status === "succeed") {
      core.setOutput("page_url", deployment.page_url);
      return {
        status: "PASS_existing_verified_pages_artifact_deployed",
        artifact_id: expected.artifactId, artifact_digest: artifact.digest,
        original_run_id: expected.runId, source_commit: expected.sourceCommit,
        deployment_run_id: context.runId, deployment_commit: context.sha,
        deployment_id: deployment.id, pages_build_version: buildVersion,
        original_artifact_rebuilt: false, original_artifact_uploaded_again: false,
        page_url: deployment.page_url,
      };
    }
    if (finalFailures.has(data.status)) throw new Error(`Pages recovery ended: ${data.status}`);
    await wait(15_000);
  }
  await request("POST /repos/{owner}/{repo}/pages/deployments/{deployment_id}/cancel", {
    deployment_id: deployment.id,
  });
  throw new Error("Bounded recovery timed out; original artifact remains unchanged");
}
