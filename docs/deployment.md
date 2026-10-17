# Deployment

Operational notes for the backend container and its continuous deployment.

The application **is deployed** to Google Cloud: the FastAPI backend runs on
Cloud Run and the React frontend is served by Firebase Hosting. This guide
covers building and running the image locally, the verified production targets,
and the automated CD workflow that deploys successful `main` commits.

Live app: <https://docassist-prod-2026.web.app/>

The production resources listed below were verified by read-only inspection with
`gcloud` and the Firebase CLI (2026-10-17). The CD workflow has completed
successful runs for `main` (GitHub Actions runs `38981079907` and `38982494643`
on 2026-10-16): the original deployment was established by hand, and subsequent
deploys are automated.

## Scope and status

- The image serves the FastAPI backend only (PostgreSQL, Qdrant, DeepSeek, and
  Sentence Transformers stay external managed services).
- **Verified production targets** (read-only inspection, 2026-10-17): project
  `docassist-prod-2026` (number `805794491895`), region `asia-southeast1`,
  Cloud Run service `docassist-api`, migration job `docassist-migrate`,
  Artifact Registry repository `docassist`, and Firebase Hosting site
  `docassist-prod-2026`. The API is publicly reachable; the frontend is at
  `https://docassist-prod-2026.web.app`.
- Billing, quotas, permissions, and free-tier allowances are **not** verified by
  inspection; do not assume them.
- Cross-origin access is configured via `CORS_ALLOWED_ORIGINS` (exact origins;
  empty by default). CORS is not authentication and does not replace the API's
  abuse controls.

## Prerequisites

- Docker with BuildKit.
- The repository checkout (build context is the repo root).

No credentials are needed to build; `uv.lock` and the pinned model revision are
baked in.

## Build the image (Linux AMD64)

Cloud Run runs `linux/amd64`, so build for that platform explicitly:

```bash
docker build --platform linux/amd64 -t production-rag:local .
```

The build uses Python 3.12 (Bookworm slim), the pinned `uv 0.13.0`, the locked
dependencies with the CPU-only PyTorch extra, and bakes the embedding model.

## Configuration

Runtime configuration uses the same environment variables as the local
application (see the README "Environment configuration" section). The most
relevant for the container:

```text
DEEPSEEK_API_KEY                 # required for /query generation
ALLOWED_COLLECTIONS              # default: fastapi
DATABASE_URL                     # hosted PostgreSQL, or POSTGRES_* for local
QDRANT_URL / QDRANT_API_KEY      # hosted Qdrant, or QDRANT_HOST/PORT for local
```

`PORT`, `HF_HOME`, `HF_HUB_OFFLINE`, and `EMBEDDING_MODEL_REVISION` are set in
the image; `PORT` defaults to `8080`.

Whenever `DATABASE_URL` is set, apply migrations separately (see below) — the
application does not run migrations at startup.

## Frontend and CORS

The React frontend reads its API base URL from `VITE_API_BASE_URL`, a public
**build-time** variable baked into the bundle (locally via `frontend/.env.local`,
which is gitignored). When unset, the frontend calls the relative `/query` path
handled by the Vite dev proxy. For a production cross-origin deployment, build
the frontend with `VITE_API_BASE_URL` set to the backend origin, and list the
frontend's origin in the backend's `CORS_ALLOWED_ORIGINS`.

`CORS_ALLOWED_ORIGINS` accepts comma-separated **exact** origins
(`scheme://host[:port]`, no path or trailing slash); `*` is rejected and there is
no substring or regex matching. CORS is **not authentication** and is not a
substitute for the request limits, collection allowlist, and rate limiting — it
is enforced by the browser, not the server.

## Run locally

The application only queries PostgreSQL, Qdrant, and DeepSeek when a request is
made. Note that the **Qdrant client is created during startup and may attempt a
compatibility check** against the configured endpoint; with no reachable Qdrant
this logs a `Failed to obtain server version` warning but does not prevent
startup.

`/health` is **shallow**: it returns `{"status": "ok"}` when the process is
serving and does **not** verify PostgreSQL, Qdrant, DeepSeek, or the embedding
model. A dummy DeepSeek key is enough to start the app and check health:

```bash
docker run --rm \
  -e DEEPSEEK_API_KEY=dummy \
  -e ALLOWED_COLLECTIONS=fastapi \
  -p 8080:8080 \
  production-rag:local
```

Check health from another shell:

```bash
curl -fsS http://localhost:8080/health
```

To exercise `/query`, provide real `DATABASE_URL`, `QDRANT_URL`/`QDRANT_API_KEY`,
and `DEEPSEEK_API_KEY` for a reachable environment. Never bake secrets into the
image; pass them at run time.

## Baked model

The embedding model `BAAI/bge-small-en-v1.5` is downloaded at build time into
`HF_HOME=/opt/hf` at the immutable revision
`5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`. The runtime sets
`EMBEDDING_MODEL_REVISION` to the same revision and `HF_HUB_OFFLINE=1`, so the
application loads the baked snapshot and cannot download models at run time
(`local_files_only=True`).

**Changing the model revision** can change embedding vectors and invalidates
existing vectors in Qdrant. If you bump it, review embedding-version
compatibility and re-ingest the corpus; update both `HF_MODEL_REVISION`
(build argument) and `EMBEDDING_MODEL_REVISION` (runtime environment) together.

## Database migrations

Migrations run **separately** from the application using the same image, and
require a reachable PostgreSQL:

```bash
docker run --rm \
  -e DATABASE_URL=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require \
  --entrypoint alembic \
  production-rag:local upgrade head
```

`alembic/` and `alembic.ini` are included for this. Online migrations use
`DATABASE_URL`. Offline SQL generation (`--sql`) is not wired to the runtime
configuration and must not be relied on.

## Inspect the image

```bash
docker image inspect production-rag:local --format '{{.Size}}'
docker run --rm --entrypoint python production-rag:local \
  -c "import torch, production_rag; print(torch.__version__, torch.cuda.is_available())"
```

## Troubleshooting

- **Model fails to load**: confirm the snapshot exists under
  `/opt/hf/hub/models--BAAI--bge-small-en-v1.5/snapshots/<revision>` and that
  `EMBEDDING_MODEL_REVISION` matches it. `HF_HUB_OFFLINE=1` makes any missing
  file fail loudly rather than downloading.
- **`libgomp` error from PyTorch**: the runtime image must include `libgomp1`.
- **Permission errors reading the model**: `/opt/hf` must be readable by the
  non-root `appuser`.
- **Wrong port**: the process binds `0.0.0.0:${PORT:-8080}`.

## Production environment

Verified by read-only inspection; this is the current state, not a target to
create.

| Component | Value |
| --- | --- |
| GCP project | `docassist-prod-2026` (number `805794491895`) |
| Region | `asia-southeast1` |
| Cloud Run service | `docassist-api` → `https://docassist-api-e7qlmgmocq-as.a.run.app` |
| Migration job | `docassist-migrate` (`alembic upgrade head`) |
| Artifact Registry | `asia-southeast1-docker.pkg.dev/docassist-prod-2026/docassist/docassist-api` |
| Runtime service account | `docassist-cloud-run@docassist-prod-2026.iam.gserviceaccount.com` |
| Firebase Hosting | site `docassist-prod-2026` → `https://docassist-prod-2026.web.app` |
| Runtime secrets (Secret Manager) | `DATABASE_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `DEEPSEEK_API_KEY` |

Service characteristics: public (`allUsers` → `roles/run.invoker`), scale-to-zero,
`2 GiB` memory, `1` CPU, concurrency `5`, request timeout `300s`, startup CPU
boost enabled. The service-level and revision-level maximum-instance settings
differ, so the CD workflow does not pass min/max instance flags and leaves the
effective scaling untouched. The frontend inlines its build-time
`VITE_API_BASE_URL`, so it must be rebuilt whenever the API URL changes.

### Cloud Run operational notes

- Cloud Run sets `PORT`; the container honors it and binds `0.0.0.0`.
- Run one Uvicorn worker per instance: the embedding model is loaded per
  instance/worker, and the in-memory rate limiter is per instance — it is
  best-effort, not a global limit.
- The first request after a scale-to-zero cold start can take well over 20
  seconds (PyTorch import plus model load); health checks must retry.
- Client IPs behind Cloud Run require `RATE_LIMIT_TRUST_CLOUD_RUN_X_FORWARDED_FOR`
  only after verifying the proxy header chain (see the README rate-limiting
  section).
- Set Cloud Run memory to at least 1 GiB (2 GiB is safer) for PyTorch plus the
  model.
- The console OpenTelemetry exporter writes span JSON to stdout, which Cloud Run
  forwards to Cloud Logging.
- Do not modify the public invoker IAM policy during routine deployments: verify
  the service is already public and preserve it.

## Continuous deployment

`.github/workflows/cd.yml` deploys a commit to production. It does not run tests:
it is triggered only when the `CI` workflow **completes successfully for a push
to `main`**, and it deploys exactly the commit CI ran on
(`github.event.workflow_run.head_sha`) — never `github.sha` or a pull-request
head.

Security conditions (all required; the job fails closed otherwise):

- the repository is exactly `S84v/production-rag`;
- the upstream conclusion is `success`;
- the upstream event is `push`;
- the upstream branch is `main`;
- the upstream head repository is this repository.

This excludes pull requests and forks. In addition, the Workload Identity
Federation provider is conditioned on the repository and `refs/heads/main`.
Workflow permissions are `contents: read`, plus `id-token: write` on the deploy
job only; deployments are serialized (`concurrency: cd-main`, no
cancel-in-progress) so a running migration or traffic shift is never cancelled.

**Freshness gate.** Successful CI runs can complete out of order, so an older
run could otherwise deploy after a newer commit has already reached `main`. A
small read-only preflight job (`contents: read` only, no cloud credentials)
compares the CI run's `head_sha` with the current `refs/heads/main` SHA before
any cloud authentication. If they differ, that successful CI run is stale: the
preflight reports `proceed=false` and the deployment job is skipped cleanly,
while the newer commit's own CI run triggers a separate CD run that deploys it.
If the current `main` SHA cannot be read, the preflight fails closed and nothing
is deployed. The gate never changes which commit is deployed: the deploy job
still checks out and ships the exact `head_sha` CI tested.

Sequence:

1. (preflight job) Confirm the CI run's exact commit is still the head of
   `main`; skip the deployment cleanly when it is not, and fail closed when the
   current `main` SHA cannot be read.
2. Validate required configuration and assert the expected project/region/
   service/job/repository/Hosting targets before any cloud mutation.
3. Authenticate with OIDC → Workload Identity Federation (no JSON keys).
4. Build the `Dockerfile` for `linux/amd64`, push a commit-SHA-tagged image to
   the Artifact Registry repository, then resolve its immutable digest.
5. Update `docassist-migrate` to the digest and execute `alembic upgrade head`
   separately from application startup; poll the execution until it succeeds. A
   failed or incomplete migration stops the workflow before any deploy.
6. Deploy the digest to `docassist-api` with **no production traffic**, tagged
   `sha-<commit>`.
7. Verify the tagged revision: a retrying `/health` check (cold start) and a
   disallowed-collection `POST /query` expecting `404` (no generation, no data
   mutation).
8. Promote the verified revision to 100% and re-check the stable service URL. If
   that check fails, traffic is restored to the previously serving revision.
9. Build the frontend with `VITE_API_BASE_URL` set to the deployed API URL
   (`npm ci` then `npm run build`) and deploy `frontend/dist` to a uniquely named
   temporary preview channel with a short expiration, using the pinned Firebase
   CLI and the federated credentials.
10. Verify the preview URL: the root responds, the JS bundle is identified and
    downloaded, and the bundle contains the expected API URL. This is a static
    hosting check only — no generation request is made and the preview origin is
    not added to CORS.
11. Promote the verified preview version to the live channel with
    `firebase hosting:clone`, then verify the stable live URL.

### Required GitHub configuration

Non-secret repository (or `production` environment) **variables**:

| Variable | Value |
| --- | --- |
| `GCP_PROJECT_ID` | `docassist-prod-2026` |
| `GCP_REGION` | `asia-southeast1` |
| `GAR_REPOSITORY` | `docassist` |
| `GAR_IMAGE` | `docassist-api` |
| `CLOUD_RUN_SERVICE` | `docassist-api` |
| `CLOUD_RUN_JOB` | `docassist-migrate` |
| `CLOUD_RUN_RUNTIME_SA` | `docassist-cloud-run@docassist-prod-2026.iam.gserviceaccount.com` |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | the CD deploy service account (see below) |
| `WIF_PROVIDER` | `projects/805794491895/locations/global/workloadIdentityPools/<pool>/providers/<provider>` |
| `FIREBASE_PROJECT_ID` | `docassist-prod-2026` |
| `APP_NAME` | `DocAssist` |
| `ALLOWED_COLLECTIONS` | `fastapi` |
| `MAX_OUTPUT_TOKENS` | `1024` |
| `MAX_CONTEXT_CHARACTERS` | `12000` |
| `RATE_LIMIT_REQUESTS` | `10` |
| `RATE_LIMIT_TRUST_CLOUD_RUN_X_FORWARDED_FOR` | `false` |
| `CORS_ALLOWED_ORIGINS` | `https://docassist-prod-2026.web.app` |

The values above are the ones currently set on the deployed service; the
workflow reproduces them on each deploy. **No GitHub secrets are needed** for
cloud authentication once WIF is configured — runtime secrets are referenced
from Secret Manager by name and version, never inlined.

### IAM and workload identity

The deploy service account should hold least-privilege access, scoped to the
repository where possible:

- `roles/artifactregistry.writer` on the `docassist` Artifact Registry
  repository (push images);
- `roles/run.developer` on the project (update the service and job, execute the
  job);
- `roles/iam.serviceAccountUser` on
  `docassist-cloud-run@docassist-prod-2026.iam.gserviceaccount.com` (deploy as
  the runtime account);
- Firebase Hosting deployment permission (for example
  `roles/firebasehosting.admin`) plus `roles/serviceusage.serviceUsageConsumer`.

Do not grant `roles/owner`. The runtime service account `docassist-cloud-run@`
already holds `roles/secretmanager.secretAccessor` on the four secrets.

Workload Identity Federation: create an OIDC provider for
`https://token.actions.githubusercontent.com` with these attribute mappings:

```text
google.subject           = assertion.sub
attribute.repository     = assertion.repository
attribute.repository_id  = assertion.repository_id
attribute.ref            = assertion.ref
attribute.workflow_ref   = assertion.workflow_ref
```

and an attribute condition that pins the provider to this immutable repository
ID, this branch, and the CD workflow itself:

```text
assertion.repository_id == '1326833407'
  && assertion.ref == 'refs/heads/main'
  && assertion.workflow_ref == 'S84v/production-rag/.github/workflows/cd.yml@refs/heads/main'
```

`cd.yml` is invoked directly (via `workflow_run`, not as a reusable workflow),
so `assertion.workflow_ref` identifies exactly this workflow file on `main`.
Grant `roles/iam.workloadIdentityUser` on the deploy service account to the
matching principal set:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  DEPLOY_SA@docassist-prod-2026.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/805794491895/locations/global/workloadIdentityPools/POOL/attribute.repository_id/1326833407"
```

`sts.googleapis.com` must be enabled (it is not currently enabled). The
repository, branch, and workflow restrictions above keep the existing
event/repository protections intact; the workflow's own job guard additionally
requires a `push` event and a successful CI conclusion.

### Rollback and migrations

- **Migrations are forward-only** and must be backward-compatible with the
  previous application revision (expand/contract), because traffic can be rolled
  back to that revision after a migration has already run. Never run
  `alembic downgrade` against production.
- A migration failure stops the workflow before deployment.
- A health failure before promotion leaves existing traffic untouched (the new
  revision was deployed with `--no-traffic`).
- If the stable-URL check after promotion fails, the workflow restores traffic
  to the previously serving revision and fails.
- **Backend rollback:** shift traffic back with
  `gcloud run services update-traffic docassist-api --region asia-southeast1 --to-revisions <previous-revision>=100`,
  or redeploy an earlier commit-SHA image.
- **Frontend promotion:** the workflow stages the build on a temporary preview
  channel, verifies it, then promotes that exact version to `live` with
  `firebase hosting:clone <site>:<channel> <site>:live`. A failed preview check
  prevents promotion.
- **Frontend rollback:** there is no `firebase hosting:rollback` CLI command.
  Recover by one of:
  - cloning a known-good channel into `live`, for example
    `firebase hosting:clone docassist-prod-2026:<known-good-channel> docassist-prod-2026:live`;
  - redeploying a known-good commit (build it with the same `VITE_API_BASE_URL`
    and run `firebase deploy --only hosting`); or
  - using the Firebase Console **Hosting → Release history → Roll back** action,
    which republishes a previous release to `live`.
- **No automatic frontend rollback:** if the final live-URL check fails *after*
  promotion, the workflow fails but does **not** roll the live site back — the
  promotion has already replaced the previous release, and the backend stays
  live. Recover manually with one of the methods above. (Backend traffic, by
  contrast, is restored automatically to the previous revision when the stable
  backend URL check fails.)

### First run (operator bootstrap)

Before the first automatic deployment:

1. Confirm billing/budget alerts remain in place (do not change them).
2. Enable `sts.googleapis.com` if it is not enabled.
3. Create the deploy service account and grant the roles above.
4. Create the WIF pool/provider with the repository and `refs/heads/main`
   condition, and bind it to the deploy account.
5. Create the GitHub `production` environment (optionally with required
   reviewers) and set the variables above.
6. Confirm the Artifact Registry repository and the four Secret Manager secrets
   exist (they do).
7. Merge or push a trivial change to `main` so CI runs; CD starts only after CI
   succeeds.
