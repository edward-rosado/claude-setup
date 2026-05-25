---
name: azure-container-app-revision-verification
description: "Verify new Container App revisions are actually running — deploy CI can succeed while container crashes silently"
user-invocable: false
origin: auto-extracted
---

# Azure Container App Revision Verification

**Extracted:** 2026-03-22
**Context:** Deploying .NET APIs to Azure Container Apps via CI/CD

## Problem
Azure Container Apps deploys can report success (image pushed to ACR, `az containerapp update` completes) while the new revision fails to start. The old revision continues serving traffic silently. You can push multiple commits thinking they're live, but nothing changes in production.

## Solution
After every deploy, verify the new revision is active:

```bash
az containerapp show \
  --name $APP_NAME \
  --resource-group $RG \
  --query "{latestReady:properties.latestReadyRevisionName, latest:properties.latestRevisionName}" \
  -o json
```

If `latestReady` != `latest`, the new revision is failing. Check why:

```bash
az containerapp logs show \
  --name $APP_NAME \
  --resource-group $RG \
  --tail 50
```

Common causes:
- **Missing env vars/secrets** — new code references config not set in Container App
- **Startup exceptions** — `throw` in Program.cs prevents container from starting
- **Health check failures** — `/health/live` endpoint unreachable
- **Missing files** — config files outside Docker build context not copied into image

## When to Use
- After any API deploy to Azure Container Apps
- When production behavior doesn't match pushed code
- When `az containerapp logs` shows old log entries despite new pushes
- When multiple deploys "succeed" but nothing changes
