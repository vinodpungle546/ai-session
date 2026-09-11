#!/usr/bin/env bash
# Deploy the payee demo to Azure Container Apps.
#
# Idempotent: every resource is looked up before it is created, and an existing
# container app is updated in place (new secrets, new image revision) instead of
# failing. Safe to re-run after every code change.
#
#   bash deploy/azure.sh                 # deploy (asks for confirmation)
#   DRY_RUN=1 bash deploy/azure.sh       # print the plan; change nothing
#   ASSUME_YES=1 bash deploy/azure.sh    # no prompt (CI / non-interactive)
#
# Configuration comes from the environment, falling back to payee-demo/.env.
# Nothing secret is ever echoed; dry-run output masks secret values.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- load .env (explicit env vars win) -----------------------------------
ENV_FILE="${ENV_FILE:-$PROJECT_DIR/.env}"
if [[ -f "$ENV_FILE" ]]; then
  # Snapshot anything already exported so the shell environment overrides .env.
  _preset="$(export -p)"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  eval "$_preset"
fi

# --- settings, with sensible defaults ------------------------------------
RESOURCE_GROUP="${RESOURCE_GROUP:-payee-demo-rg}"
LOCATION="${LOCATION:-centralindia}"
APP_NAME="${APP_NAME:-payee-demo}"
ENV_NAME="${ENV_NAME:-${APP_NAME}-env}"
IMAGE_REPO="${IMAGE_REPO:-payee-demo}"
# Slim dependency set: drops the Phoenix server (never imported in-container,
# traces go to Langfuse) — 660 MB smaller, which is paid on every cold start.
REQUIREMENTS="${REQUIREMENTS:-requirements-container.txt}"
# managed identity (default, policy-friendly) or admin (ACR admin user)
REGISTRY_AUTH="${REGISTRY_AUTH:-identity}"

MODEL_PROVIDER="${MODEL_PROVIDER:-openai_compatible}"
MODEL_NAME="${MODEL_NAME:-gpt-4o-mini}"
MODEL_BASE_URL="${MODEL_BASE_URL:-}"
LANGFUSE_HOST="${LANGFUSE_HOST:-https://cloud.langfuse.com}"

DRY_RUN="${DRY_RUN:-0}"

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
die()  { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

# Replace every secret value with *** before anything is printed.
mask() {
  local s="$*" v
  for v in MODEL_API_KEY LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY ACR_PASSWORD; do
    [[ -n "${!v:-}" ]] && s="${s//${!v}/***}"
  done
  printf '%s' "$s"
}

# Mutating commands go through run(); read-only lookups run for real even in
# dry-run, so the plan printed is the plan that would actually execute.
run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '    [dry-run] %s\n' "$(mask "$@")"
  else
    "$@"
  fi
}

# exists <az show command...>
#   0 = exists, 1 = not found, 2 = permission denied. Treating "forbidden"
#   as "absent" would send the script off to create something it isn't allowed
#   to, failing late with a less useful error.
exists() {
  local err
  if err="$("$@" -o none 2>&1)"; then return 0; fi
  if grep -qiE "AuthorizationFailed|does not have authorization|Forbidden" <<<"$err"; then
    return 2
  fi
  return 1
}

# --- preflight -------------------------------------------------------------
command -v az >/dev/null || die "Azure CLI not found. Install: https://aka.ms/installazurecli"
az account show >/dev/null 2>&1 || die "Not logged in. Run: az login"
[[ -n "${AZ_SUBSCRIPTION:-}" ]] && az account set --subscription "$AZ_SUBSCRIPTION"

missing=()
for v in MODEL_API_KEY LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY; do
  [[ -n "${!v:-}" ]] || missing+=("$v")
done
((${#missing[@]} == 0)) || die "Missing required env vars: ${missing[*]} (set them or add to $ENV_FILE)"

SUB_NAME="$(az account show --query name -o tsv)"
SUB_ID="$(az account show --query id -o tsv)"

# ACR names are global and must be 5-50 lowercase alphanumerics. Derive a stable
# suffix from the subscription so re-runs reuse the same registry.
ACR_NAME="${ACR_NAME:-payeedemo$(printf '%s' "$SUB_ID" | shasum | cut -c1-8)}"
IMAGE_TAG="${IMAGE_TAG:-$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || echo manual)-$(date +%Y%m%d%H%M%S)}"
IMAGE="${ACR_NAME}.azurecr.io/${IMAGE_REPO}:${IMAGE_TAG}"

say "Deployment plan"
info "subscription   : $SUB_NAME ($SUB_ID)"
info "resource group : $RESOURCE_GROUP  ($LOCATION)"
info "registry       : $ACR_NAME  (auth: $REGISTRY_AUTH)"
info "environment    : $ENV_NAME"
info "app            : $APP_NAME  (scale 0-1, ingress external :8000)"
info "image          : $IMAGE"
info "model          : $MODEL_PROVIDER / $MODEL_NAME"
info "telemetry      : langfuse @ $LANGFUSE_HOST"
[[ "$DRY_RUN" == "1" ]] && info "mode           : DRY RUN — nothing will be created or changed"

# --- permission preflight: fail now, not after a 10-minute image build ------
ME="$(az account show --query user.name -o tsv)"
set +e; exists az group show -n "$RESOURCE_GROUP"; rg_state=$?; set -e
RG_PREEXISTING=0
case $rg_state in
  0) RG_PREEXISTING=1 ;;
  1) ;;  # genuinely absent: will be created
  2)
    # Azure returns 403 for groups you cannot see, whether or not they exist,
    # so "no access" here also means "cannot create it".
    visible="$(az group list --query '[].name' -o tsv 2>/dev/null | paste -sd, - || true)"
    die "No access to resource group '$RESOURCE_GROUP' in subscription '$SUB_NAME'.
       You cannot read or create it with your current role.
       Groups you can use: ${visible:-none}
       Either set RESOURCE_GROUP to one of those (see the teardown warning in
       deploy/README.md first), or ask the subscription owner for Contributor on
       a new group." ;;
esac

if [[ "$REGISTRY_AUTH" == "identity" && "${SKIP_ROLE_CHECK:-0}" != "1" ]]; then
  # Managed-identity pull needs an AcrPull role assignment, which only Owner /
  # User Access Administrator / RBAC Administrator can create. Contributor cannot.
  can_assign="$(az role assignment list --assignee "$ME" --all --include-groups \
      --query "[?roleDefinitionName=='Owner' || roleDefinitionName=='User Access Administrator' || roleDefinitionName=='Role Based Access Control Administrator'] | length(@)" \
      -o tsv 2>/dev/null || echo 0)"
  if [[ "${can_assign:-0}" == "0" ]]; then
    die "REGISTRY_AUTH=identity needs permission to create role assignments
       (Owner or User Access Administrator), and '$ME' has neither.
       Re-run with REGISTRY_AUTH=admin to use the ACR admin user instead.
       (Set SKIP_ROLE_CHECK=1 if your rights come from somewhere this check cannot see.)"
  fi
fi

# This creates billable resources. Make the target subscription an explicit choice.
if [[ "$DRY_RUN" != "1" && "${ASSUME_YES:-0}" != "1" ]]; then
  [[ -t 0 ]] || die "Refusing to deploy non-interactively without ASSUME_YES=1."
  read -r -p $'\n    Create/update these resources in "'"$SUB_NAME"$'"? [y/N] ' ans
  [[ "$ans" =~ ^[Yy]$ ]] || die "Aborted by user."
fi

# --- resource group ----------------------------------------------------------
say "Resource group"
if [[ "$RG_PREEXISTING" == "1" ]]; then
  info "exists: $RESOURCE_GROUP  (pre-existing — this script will NOT offer to delete it)"
else
  run az group create -n "$RESOURCE_GROUP" -l "$LOCATION" -o none
fi

# --- container registry ------------------------------------------------------
say "Container registry"
if az acr show -n "$ACR_NAME" -g "$RESOURCE_GROUP" >/dev/null 2>&1; then
  info "exists: $ACR_NAME"
else
  run az acr create -n "$ACR_NAME" -g "$RESOURCE_GROUP" -l "$LOCATION" --sku Basic -o none
fi

# --- build in Azure (no local docker push) -----------------------------------
# The build context honours .dockerignore, which excludes .env and .venv, so no
# secrets and no local virtualenv are uploaded.
say "Build image in ACR"
run az acr build \
  --registry "$ACR_NAME" \
  --image "${IMAGE_REPO}:${IMAGE_TAG}" \
  --build-arg "REQUIREMENTS=${REQUIREMENTS}" \
  --file "$PROJECT_DIR/Dockerfile" \
  "$PROJECT_DIR"

# --- container apps environment ---------------------------------------------
say "Container Apps environment"
if az containerapp env show -n "$ENV_NAME" -g "$RESOURCE_GROUP" >/dev/null 2>&1; then
  info "exists: $ENV_NAME"
else
  run az containerapp env create -n "$ENV_NAME" -g "$RESOURCE_GROUP" -l "$LOCATION" -o none
fi

# --- secrets and environment -------------------------------------------------
# Secret names must be lowercase alphanumerics and hyphens.
SECRETS=(
  "model-api-key=${MODEL_API_KEY}"
  "langfuse-public-key=${LANGFUSE_PUBLIC_KEY}"
  "langfuse-secret-key=${LANGFUSE_SECRET_KEY}"
)
ENV_VARS=(
  "MODEL_API_KEY=secretref:model-api-key"
  "LANGFUSE_PUBLIC_KEY=secretref:langfuse-public-key"
  "LANGFUSE_SECRET_KEY=secretref:langfuse-secret-key"
  "TELEMETRY_BACKEND=langfuse"
  "LANGFUSE_HOST=${LANGFUSE_HOST}"
  "MODEL_PROVIDER=${MODEL_PROVIDER}"
  "MODEL_NAME=${MODEL_NAME}"
  "GROUNDING_ENABLED=true"
  "GUARDRAILS_ENABLED=true"
)
[[ -n "$MODEL_BASE_URL" ]] && ENV_VARS+=("MODEL_BASE_URL=${MODEL_BASE_URL}")

REGISTRY_ARGS=(--registry-server "${ACR_NAME}.azurecr.io")
if [[ "$REGISTRY_AUTH" == "admin" ]]; then
  run az acr update -n "$ACR_NAME" --admin-enabled true -o none
  if [[ "$DRY_RUN" == "1" ]]; then
    ACR_USER="<acr-admin-user>"; ACR_PASSWORD="<acr-admin-password>"
  else
    ACR_USER="$(az acr credential show -n "$ACR_NAME" --query username -o tsv)"
    ACR_PASSWORD="$(az acr credential show -n "$ACR_NAME" --query 'passwords[0].value' -o tsv)"
  fi
  REGISTRY_ARGS+=(--registry-username "$ACR_USER" --registry-password "$ACR_PASSWORD")
else
  # System-assigned identity; the CLI grants it AcrPull on the registry.
  REGISTRY_ARGS+=(--registry-identity system)
fi

# --- create or update the app ------------------------------------------------
say "Container app"
if az containerapp show -n "$APP_NAME" -g "$RESOURCE_GROUP" >/dev/null 2>&1; then
  info "exists: $APP_NAME — updating in place"
  run az containerapp secret set -n "$APP_NAME" -g "$RESOURCE_GROUP" --secrets "${SECRETS[@]}" -o none
  # A new image tag always produces a new revision, which also picks up the
  # refreshed secret values above.
  run az containerapp update -n "$APP_NAME" -g "$RESOURCE_GROUP" \
    --image "$IMAGE" \
    --min-replicas 0 --max-replicas 1 \
    --set-env-vars "${ENV_VARS[@]}" \
    -o none
else
  run az containerapp create -n "$APP_NAME" -g "$RESOURCE_GROUP" \
    --environment "$ENV_NAME" \
    --image "$IMAGE" \
    "${REGISTRY_ARGS[@]}" \
    --target-port 8000 --ingress external \
    --min-replicas 0 --max-replicas 1 \
    --secrets "${SECRETS[@]}" \
    --env-vars "${ENV_VARS[@]}" \
    -o none
fi

# --- result ------------------------------------------------------------------
say "Done"
if [[ "$DRY_RUN" == "1" ]]; then
  info "dry run complete — no resources were created or changed"
else
  FQDN="$(az containerapp show -n "$APP_NAME" -g "$RESOURCE_GROUP" \
          --query properties.configuration.ingress.fqdn -o tsv)"
  info "app URL : https://${FQDN}"
  info "warm it : bash deploy/warm.sh ${FQDN}"
  info "logs    : az containerapp logs show -n $APP_NAME -g $RESOURCE_GROUP --follow"
fi
say "Teardown (stop billing)"
if [[ "$RG_PREEXISTING" == "1" ]]; then
  info "The group '$RESOURCE_GROUP' existed before this script ran and may hold"
  info "other people's resources. Do NOT delete the group. Remove only what this"
  info "deploy created:"
  info "  az containerapp delete     -n $APP_NAME -g $RESOURCE_GROUP --yes"
  info "  az containerapp env delete -n $ENV_NAME -g $RESOURCE_GROUP --yes"
  info "  az acr delete              -n $ACR_NAME -g $RESOURCE_GROUP --yes"
else
  info "This script created '$RESOURCE_GROUP', so it is safe to remove whole:"
  info "  az group delete -n $RESOURCE_GROUP --yes --no-wait"
fi
