---
name: azure-durable-functions-linux
description: "Azure Linux Consumption plan lacks Microsoft.AspNetCore.App; use Worker.Extensions.Http (not Http.AspNetCore) to avoid silent 500 crashes on every invocation."
user-invocable: false
origin: auto-extracted
---

# Azure Durable Functions on Linux Consumption Plan

## Critical: No ASP.NET Core Framework

Azure Linux Consumption plan does NOT include `Microsoft.AspNetCore.App` shared framework.

**Symptoms:** Functions are discovered (39 found), worker starts, but every function invocation returns 500 with empty body. No error in App Insights — the crash is invisible.

**Root cause:** `runtimeconfig.json` declares dependency on `Microsoft.AspNetCore.App` which isn't installed on the Azure Functions Linux host.

**Fix:**
```xml
<!-- WRONG — crashes on Azure Linux Consumption -->
<FrameworkReference Include="Microsoft.AspNetCore.App" />
<PackageReference Include="Microsoft.Azure.Functions.Worker.Extensions.Http.AspNetCore" Version="2.0.*" />

<!-- CORRECT — works everywhere -->
<PackageReference Include="Microsoft.Azure.Functions.Worker.Extensions.Http" Version="3.2.*" />
```

```csharp
// WRONG — requires ASP.NET Core
builder.ConfigureFunctionsWebApplication();

// CORRECT — just build and run
var builder = FunctionsApplication.CreateBuilder(args);
// no ConfigureFunctionsWebApplication()
var app = builder.Build();
app.Run();
```

Use `HttpRequestData`/`HttpResponseData`, not `HttpRequest`/`IActionResult`.

**After changing csproj:** ALWAYS clean rebuild (`rm -rf bin obj`) to regenerate `runtimeconfig.json`. Stale runtimeconfig with old framework refs will persist otherwise.

## Deployment: func CLI, Not config-zip

`az functionapp deployment source config-zip` sets `WEBSITE_RUN_FROM_PACKAGE` which mounts the zip read-only. The Azure Functions host cannot read `.azurefunctions/` properly from the mounted filesystem.

**Use instead:** `func azure functionapp publish <app-name> --no-build --dotnet-isolated`

This deploys via SCM/Kudu (unpacks files) and performs trigger sync.

## WorkerExtensions: Required for Function Discovery

The Functions SDK generates host-side extension DLLs during `dotnet build` at:
```
obj/{Config}/net9.0/WorkerExtensions/bin/Release/net8.0/
```

These DLLs (DurableTask, Queues, Rpc, etc.) must be in `.azurefunctions/` in the deployed package. Without them, the host shows "0 functions found (Custom)" and never starts the worker.

**CI workflow pattern (MUST be single job — GitHub Actions artifact upload strips dot-prefixed dirs):**
1. `dotnet build` generates WorkerExtensions in obj/
2. `dotnet publish --output ./bin/output` — copies DLLs but NOT metadata
3. Copy `obj/*/functions.metadata` and `worker.config.json` to `bin/output/`
4. Copy `obj/*/WorkerExtensions/bin/Release/net8.0/` to `bin/output/.azurefunctions/`
5. Copy `function.deps.json` from nested `bin/` subdirectory to `.azurefunctions/` root
6. Deploy with `func azure functionapp publish --no-build` from `bin/output/`

**CRITICAL: Use a single CI job.** A two-job workflow requires artifact upload/download which strips `.azurefunctions/`. The `_azurefunctions` rename workaround does NOT work — the restored structure is subtly different from what `func start` produces.

**Files `dotnet publish` does NOT copy (must copy from obj/ manually):**
- `functions.metadata` — function definitions for host discovery
- `worker.config.json` — worker language config for host
- `.azurefunctions/` — host-side extension DLLs + `function.deps.json`

## Debugging Silent 500s

If functions are discovered but every invocation returns 500 with empty body:
1. Check `runtimeconfig.json` for unexpected framework references
2. Check `AzureFunctionsDiagnosticEvents{YYYYMM}` table in storage account
3. Check App Insights for "Executed Failed" without error detail — means worker-side crash
4. Try adding a startup error table writer in Program.cs catch block
5. App Insights only captures HOST-side logs, not worker-side. OTel goes to Grafana.

## Azure Settings

```
FUNCTIONS_WORKER_RUNTIME=dotnet-isolated
FUNCTIONS_EXTENSION_VERSION=~4
WEBSITE_USE_PLACEHOLDER_DOTNETISOLATED=1
linuxFxVersion=DOTNET-ISOLATED|9
```

Note: `DOTNET-ISOLATED|9` (not `9.0`) — Azure CLI validates against `['10', '9', '8', '7', '6']`.

## Scope Note

The ASP.NET Core restriction applies to **all** Azure Functions on Linux Consumption plan, not just Durable Functions. On Premium (EP1) or Dedicated (App Service) plans, ASP.NET Core IS available — you can use `ConfigureFunctionsWebApplication()` and `HttpRequest`/`IActionResult` there. Only Consumption plan lacks the shared framework.

## Related: runtimeconfig.json Staleness

After ANY csproj framework reference change, stale `bin/output/` from `func start` will retain the OLD `runtimeconfig.json`. ALWAYS `rm -rf bin/output bin/Debug` before rebuilding. This caused hours of debugging — the fix was applied but the stale runtimeconfig kept requesting `Microsoft.AspNetCore.App`.
