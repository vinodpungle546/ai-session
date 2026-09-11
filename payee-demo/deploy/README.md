# Deploying to Azure Container Apps

`deploy/azure.sh` builds the image in Azure Container Registry and deploys it to
Azure Container Apps with scale-to-zero. It is idempotent: re-running it
updates the existing app (new secrets, new image revision) rather than failing.

## Prerequisites

- **Azure CLI** 2.60 or later, logged in: `az login`
  (verified against 2.89.1; `az containerapp` is built in, no extension needed)
- A subscription where you can create resource groups — **check which one is
  active before deploying**: `az account show --query name -o tsv`.
  Switch with `az account set --subscription "<name or id>"`, or pass
  `AZ_SUBSCRIPTION=...` to the script.
- Resource providers `Microsoft.App`, `Microsoft.OperationalInsights` and
  `Microsoft.ContainerRegistry` registered (usually already are):
  `az provider register -n Microsoft.App --wait`
- **No local Docker needed** — the image is built server-side by `az acr build`.

## Required environment variables

The script reads the environment first, then falls back to `payee-demo/.env`.

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MODEL_API_KEY` | **yes** | — | stored as a Container Apps **secret** |
| `LANGFUSE_PUBLIC_KEY` | **yes** | — | secret |
| `LANGFUSE_SECRET_KEY` | **yes** | — | secret |
| `LANGFUSE_HOST` | recommended | `https://cloud.langfuse.com` | **must match your Langfuse region** — e.g. `https://jp.cloud.langfuse.com`. The wrong region returns 401 and traces silently vanish |
| `MODEL_PROVIDER` | no | `openai_compatible` | |
| `MODEL_NAME` | no | `gpt-4o-mini` | |
| `MODEL_BASE_URL` | no | provider default | passed through only if set |

Deployment settings, all optional:

| Variable | Default |
|---|---|
| `RESOURCE_GROUP` | `payee-demo-rg` |
| `LOCATION` | `centralindia` |
| `ACR_NAME` | `payeedemo` + 8 chars derived from the subscription id (stable across re-runs) |
| `APP_NAME` | `payee-demo` |
| `ENV_NAME` | `payee-demo-env` |
| `IMAGE_TAG` | `<git short sha>-<timestamp>` — unique per run, so every deploy is a new revision |
| `REQUIREMENTS` | `requirements-container.txt` — the slim set, 660 MB smaller than the full one |
| `REGISTRY_AUTH` | `identity` (system-assigned managed identity). **Needs Owner or User Access Administrator** to grant the AcrPull role — with **Contributor only, use `admin`** (ACR admin user). The script checks this before building |

The app is always deployed with `TELEMETRY_BACKEND=langfuse`,
`GROUNDING_ENABLED=true`, `GUARDRAILS_ENABLED=true`, external ingress on port
8000, and 0–1 replicas.

## Deploy

```bash
cd payee-demo

# 1. See exactly what would happen. Creates nothing; secrets are masked.
DRY_RUN=1 bash deploy/azure.sh

# 2. Deploy. Prints the plan and asks for confirmation before creating anything.
bash deploy/azure.sh
```

For CI or other non-interactive use, add `ASSUME_YES=1`; without it the script
refuses to run without a terminal, so it can never create billable resources
unattended by accident.

The last lines print the app URL. The first deploy takes roughly 8–12 minutes,
most of it the image build. Re-deploys take 4–6.

## Before a live demo

```bash
bash deploy/warm.sh            # looks the FQDN up with az
bash deploy/warm.sh <fqdn>     # or pass it directly
```

Run it **about five minutes before you present**. With `min-replicas 0` the app
sleeps when idle, and a cold start takes 20–40 seconds; `warm.sh` pays that
wait for you instead of the first person in the room.

## Check logs

```bash
# live application logs (Streamlit + app)
az containerapp logs show -n payee-demo -g payee-demo-rg --follow

# the last 100 lines, no streaming
az containerapp logs show -n payee-demo -g payee-demo-rg --tail 100

# system logs: image pulls, revision provisioning, scaling
az containerapp logs show -n payee-demo -g payee-demo-rg --type system

# revision health
az containerapp revision list -n payee-demo -g payee-demo-rg -o table
```

Traces go to Langfuse, not to these logs — check your Langfuse project for the
span tree and per-trace cost.

## Delete everything (stop billing)

> ### ⚠ Check whose resource group it is before deleting anything
> `az group delete` removes **every** resource in the group, not just this demo.
> If you deployed into a group that **already existed** — for example one shared
> with another project because you lack rights to create your own — deleting the
> group destroys that project too. The script tells you which case applies in
> its final **Teardown** section; follow that output, not memory.

**If the script created the group** (the default `payee-demo-rg`), it holds only
this demo and is safe to remove whole:

```bash
az group delete -n payee-demo-rg --yes --no-wait
az group exists -n payee-demo-rg        # prints false once deletion completes
```

**If you deployed into a pre-existing, shared group**, delete only the three
resources this deploy created, and leave the group alone:

```bash
RG=<the group you used>
az containerapp delete     -n payee-demo      -g "$RG" --yes
az containerapp env delete -n payee-demo-env  -g "$RG" --yes
az acr delete              -n <acr-name>      -g "$RG" --yes   # printed by the script
```

Deleting the environment also removes the Log Analytics workspace it created.

**What it costs while it exists:** the container app itself costs close to
nothing when scaled to zero. The standing costs are the **ACR Basic** registry
(roughly USD 5/month) and **Log Analytics** ingestion from the environment.
Delete it when the session is over.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Revision fails with an image pull / unauthorized error on first deploy | managed-identity role assignment still propagating | wait a minute and re-run the script; or use `REGISTRY_AUTH=admin` |
| `No access to resource group …` | your role does not cover that group (Azure returns 403 whether or not it exists) | use a group the error lists, or ask for Contributor on a new one |
| `REGISTRY_AUTH=identity needs permission to create role assignments` | you are Contributor, not Owner | re-run with `REGISTRY_AUTH=admin` |
| `RequestDisallowedByPolicy` on the registry or identity | a subscription policy | try `REGISTRY_AUTH=admin`, or ask the subscription owner |
| App loads but every instruction is blocked | invalid `MODEL_NAME`, so every model call fails and the guardrail fails closed | check `az containerapp show -n payee-demo -g payee-demo-rg --query properties.template.containers[0].env` |
| No traces in Langfuse | `LANGFUSE_HOST` points at the wrong region | set it to your region's host and re-run |
| First page load hangs 20–40 s | cold start from zero | run `deploy/warm.sh` beforehand |
