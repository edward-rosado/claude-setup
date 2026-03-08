---
name: dotnet
description: .NET coding conventions for this repository. Use whenever writing, modifying, or reviewing C# code, including production code, tests, domain models, data layer, and Lambda functions.
---

# .NET Conventions

## Expression-Bodied Members

Use arrow functions (expression-bodied members) whenever the body is a single expression.

```csharp
// Good
public bool CanHandle(CompanySyncMessage message) => message is VariableSyncMessage;

public async Task RunAsync(CompanySyncMessage message, CancellationToken ct)
    => await RunAsync((VariableSyncMessage)message, ct);

// Bad
public bool CanHandle(CompanySyncMessage message)
{
    return message is VariableSyncMessage;
}
```

## Primary Constructors

Use primary constructors for dependency injection instead of field assignments in production code. Test classes may use traditional constructors and fields when the test framework or base class setup works better without primary constructors — follow the existing pattern in each test file.

```csharp
// Good
public class VariableSynchronizer(
    IVariablesService variablesService,
    IDataSyncService dataSyncService,
    IOptions<SyncSettings> syncSettings,
    ILogger<VariableSynchronizer> logger) : ISynchronizer
{
    // Use parameters directly — no private fields needed
}

// Bad
public class VariableSynchronizer : ISynchronizer
{
    private readonly IVariablesService _variablesService;
    public VariableSynchronizer(IVariablesService variablesService)
    {
        _variablesService = variablesService;
    }
}
```

## Enums Over Raw Strings

Define enums for any finite set of values instead of using raw strings.

Only add `[JsonConverter(typeof(JsonStringEnumConverter))]` to enums that are serialized as JSON (e.g., enums stored in JSONB columns or returned in API responses). Do **not** add it to enums that map to integer lookup tables in the database (e.g., `SyncTypes`, `SyncStates`) — those are cast to `int` and never written as JSON strings.

```csharp
// Good — enum serialized in JSONB progress column
[JsonConverter(typeof(JsonStringEnumConverter))]
public enum SyncSource { Api, Cron }

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum FailureType { Internal, External }

// Good — enum tied to database lookup table, no JsonConverter needed
public enum SyncTypes { Client = 1, User = 2, Variable = 3, Hierarchy = 4, Admin = 5 }
public enum SyncStates { InProgress = 1, Complete = 2, Partial = 3 }

// Bad — raw strings instead of enums
public string Source { get; set; } = "Api";
public string FailureType { get; set; } = "Internal";
```

## Repository Method Naming

Prefer standard verb names (`GetAsync`, `UpdateAsync`, `DeleteAsync`, `UpsertAsync`) over method-per-query naming (`GetByX`, `UpdateForY`, `DeleteWhereZ`). This applies to all repository operations — reads, updates, deletes, and upserts.

When a method takes more than 2-3 parameters (beyond `CancellationToken` and `traceId`), use a request object instead of overloading with additional parameters. `CancellationToken` and `traceId` are infrastructure concerns — always pass them as standalone trailing parameters, not inside request objects.

```csharp
// Good — simple queries use filter parameters
Task<SyncStatusRow?> GetAsync(Guid accountLinkId, int syncTypeId, CancellationToken ct);
Task<List<SyncStatusRow>> GetAsync(Guid accountLinkId, CancellationToken ct);

// Good — complex operations use request objects
Task UpsertAsync(UpsertSyncStatusRequest request, CancellationToken ct);
Task DeleteAsync(DeleteSyncStatusRequest request, CancellationToken ct);

// Bad — overloading with too many parameters
Task UpsertAsync(Guid accountLinkId, int syncTypeId, int syncStateId, string? progress, CancellationToken ct);
Task UpsertAsync(Guid accountLinkId, int syncTypeId, int syncStateId, string? progress, bool resetFailCounts, CancellationToken ct);

// Bad — method-per-query naming
Task<SyncStatusRow?> GetByAccountLinkIdAndSyncTypeAsync(Guid accountLinkId, int syncTypeId, CancellationToken ct);
Task UpdateSyncStatusForAccountAsync(Guid accountLinkId, int syncTypeId, CancellationToken ct);
```

## Collection Expressions

Use `[]` collection expressions over `new List<T>()` or `Array.Empty<T>()`.

```csharp
// Good
var existingAttempts = progress?.Attempts ?? [];
Attempts = [new VariableSyncAttempt { ... }]

// Bad
var existingAttempts = progress?.Attempts ?? new List<VariableSyncAttempt>();
```

## Init-Only Properties for Data Models

Use `init` properties on models and DTOs. Use `record` types for truly immutable value objects.

```csharp
// Good
public class VariableSyncProgress
{
    public int LastAttempt { get; init; }
    public Dictionary<string, VariableStatus> Variables { get; init; } = new();
    public List<VariableSyncAttempt> Attempts { get; init; } = [];
}

// Bad — mutable setters on a data model
public class VariableSyncProgress
{
    public int LastAttempt { get; set; }
}
```

## Type Aliases for Disambiguation

Only use `using` aliases when there is a genuine compile-time ambiguity between two types with the same name in different imported namespaces. Do not use aliases to disambiguate a type name from a property name — C# resolves these from context.

```csharp
// Good — genuine ambiguity: both namespaces define VariableDetail
using VariableDetail = Marketing.DataManagement.Lambda.DataSync.Models.Companies.VariableDetail;

// Bad — no ambiguity: FailureType the enum vs result.FailureType the property
using DomainFailureType = Mindbody.Marketing.DataManagement.Domain.Models.Enums.FailureType;
```

## Null-Coalescing Patterns

Use `??`, `?.`, and null-coalescing assignment for concise null handling.

```csharp
// Good
var value = variable.Value ?? string.Empty;
var progress = !string.IsNullOrEmpty(syncStatus?.Progress)
    ? JsonSerializer.Deserialize<VariableSyncProgress>(syncStatus.Progress)
    : null;
var attemptNumber = (progress?.LastAttempt ?? 0) + 1;
var variables = new Dictionary<string, VariableStatus>(progress?.Variables ?? new());

// Bad
var value = variable.Value != null ? variable.Value : string.Empty;
```

## Pattern Matching

Use `is` for type checks and switch expressions for multi-branch type/value matching. For null checks, `!= null` is the prevailing pattern in this codebase.

```csharp
// Good — type check with 'is'
var isCancellation = ex is OperationCanceledException || cancellationToken.IsCancellationRequested;

// Good — null checks with != null
if (processor != null) { ... }

// Bad — avoid reflection for type checks
var isCancellation = ex.GetType() == typeof(OperationCanceledException);
```

## File-Scoped Namespaces

Always use file-scoped namespace declarations.

```csharp
// Good
namespace Marketing.DataManagement.Lambda.CompanySync.Worker.Processors.Synchronizers;

public class VariableSynchronizer { ... }

// Bad
namespace Marketing.DataManagement.Lambda.CompanySync.Worker.Processors.Synchronizers
{
    public class VariableSynchronizer { ... }
}
```

## Structured Logging

Use message templates with named placeholders — never string interpolation.

```csharp
// Good
logger.LogInformation("Starting variable sync for company {CompanyId} with {VariableCount} variables",
    companyId, message.Variables.Count);

// Bad
logger.LogInformation($"Starting variable sync for company {companyId} with {message.Variables.Count} variables");
```

## Exception Handling Order

Order catch blocks from most-specific to least-specific.

```csharp
// Good
catch (AttentiveException ex) { /* external failure */ }
catch (Exception ex) { /* internal/unknown failure */ }
```

## CancellationToken Propagation

Pass `CancellationToken` through all async method signatures. When recovering from cancellation, use `CancellationToken.None`.

```csharp
var recoveryToken = isCancellation ? CancellationToken.None : cancellationToken;
await dataSyncService.UpdateSyncStatusAsync(request, recoveryToken);
```

## Testing: Callback Capture Pattern

When you need to assert on complex objects passed to mocks, use Moq's `Callback` to capture the argument, then assert separately.

```csharp
Mindbody.Marketing.DataManagement.Data.Postgres.Models.UpsertSyncStatusRequest? capturedRequest = null;
MockSyncStatusRepository.Setup(repo => repo.UpsertAsync(
        It.Is<UpsertSyncStatusRequest>(req => req.SyncStateId == (int)SyncStates.Complete),
        It.IsAny<CancellationToken>()))
    .Callback<UpsertSyncStatusRequest, CancellationToken>(
        (req, _) => capturedRequest = req)
    .Returns(Task.CompletedTask);

await CallFunction(message);

Assert.NotNull(capturedRequest);
Assert.True(capturedRequest.ResetFailCounts);
```

## Testing: Call-Count Conditional Behavior

When a mock must behave differently on sequential calls (e.g., succeed then throw), use a counter in the `Returns` lambda.

```csharp
var callCount = 0;
MockSyncStatusRepository.Setup(repo => repo.UpsertAsync(
        It.IsAny<UpsertSyncStatusRequest>(),
        It.IsAny<CancellationToken>()))
    .Returns<UpsertSyncStatusRequest, CancellationToken>((req, _) =>
    {
        callCount++;
        if (callCount == 2)
        {
            throw new InvalidOperationException("Final status update failed");
        }
        return Task.CompletedTask;
    });
```
