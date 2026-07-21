# C# AST worker (Wave 24)

Parse-only [Roslyn](https://github.com/dotnet/roslyn) extractor used when a
**.NET SDK** (`dotnet --list-sdks` non-empty) is on PATH.

```bash
printf '%s' '{"root":"/abs","files":["MathUtil.cs"]}' | dotnet run --project cli/ucli/analyzers/csharp_ast/UfCsharpAst.csproj --verbosity quiet
```

Requires .NET SDK 8+. A runtime-only install is **not** enough — the adapter
falls back to `csharp-best-effort` regex (`UF_CSHARP_ANALYZER=regex|ast|auto`).

`bin/` / `obj/` are build output — safe to delete; first run restores NuGet packages.
