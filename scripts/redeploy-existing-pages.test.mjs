import assert from "node:assert/strict";
import test from "node:test";
import { recoverPages, validateRecovery } from "./redeploy-existing-pages.mjs";

function fixture() {
  const sourceCommit = "a".repeat(40), artifactDigest = "sha256:" + "b".repeat(64);
  const expected = { artifactId: 7, runId: 8, sourceCommit, artifactDigest };
  return {
    expected, repositoryId: 9,
    artifact: { id: 7, name: "github-pages", expired: false, digest: artifactDigest,
      workflow_run: { id: 8, repository_id: 9, head_repository_id: 9, head_sha: sourceCommit } },
    run: { id: 8, head_sha: sourceCommit, head_branch: "main" },
    jobs: [{ name: "build", conclusion: "success" }],
    comparison: { status: "ahead" },
  };
}

test("recovery rejects expired, changed, foreign or unbuilt artifacts", () => {
  validateRecovery(fixture());
  for (const change of [
    value => { value.artifact.expired = true; },
    value => { value.artifact.digest = "sha256:" + "c".repeat(64); },
    value => { value.artifact.workflow_run.repository_id = 10; },
    value => { value.jobs[0].conclusion = "failure"; },
    value => { value.comparison.status = "diverged"; },
  ]) {
    const value = fixture(); change(value);
    assert.throws(() => validateRecovery(value));
  }
});

function harness(statuses) {
  const value = fixture(), requests = [], outputs = {};
  const github = {
    paginate: async () => value.jobs,
    request: async (route, parameters) => {
      requests.push({ route, parameters });
      if (route.includes("/actions/artifacts/")) return { data: value.artifact };
      if (route.includes("/actions/runs/")) return { data: value.run };
      if (route.includes("/compare/")) return { data: value.comparison };
      if (route.endsWith("/cancel")) return { data: {} };
      if (route.startsWith("POST ")) return { data: { id: "unique-version", page_url: "https://example.test/" } };
      return { data: { status: statuses.shift() || "" } };
    },
  };
  const core = { getIDToken: async () => "issued-test-token",
    info() {}, setOutput(key, result) { outputs[key] = result; } };
  const context = { ref: "refs/heads/main", sha: "d".repeat(40), repo: { owner: "owner", repo: "site" },
    payload: { repository: { id: 9 } }, runId: 20, runAttempt: 1 };
  return { github, core, context, expected: value.expected, requests, outputs };
}

test("pending then success reuses the same artifact with a fresh deployment identity", async () => {
  const args = harness(["", "succeed"]);
  const proof = await recoverPages({ ...args, wait: async () => {} });
  assert.equal(proof.artifact_id, 7);
  assert.equal(proof.original_artifact_rebuilt, false);
  assert.equal(proof.original_artifact_uploaded_again, false);
  const creation = args.requests.find(item => item.route.startsWith("POST "));
  assert.equal(creation.parameters.artifact_id, 7);
  assert.equal(creation.parameters.oidc_token, "issued-test-token");
  assert.match(creation.parameters.pages_build_version, /-20-1$/);
  assert.ok(!args.requests.some(item => /upload|download|dispatch/.test(item.route)));
});

test("permanent deployment failure is not reported as success", async () => {
  await assert.rejects(recoverPages({ ...harness(["deployment_content_failed"]), wait: async () => {} }),
    /deployment_content_failed/);
});

test("a bounded timeout cancels only the newly created deployment", async () => {
  const args = harness([""]);
  let time = 0;
  await assert.rejects(recoverPages({ ...args, now: () => time, wait: async () => { time = 2; }, timeout: 1 }),
    /timed out/);
  const canceled = args.requests.find(item => item.route.endsWith("/cancel"));
  assert.equal(canceled.parameters.deployment_id, "unique-version");
});
