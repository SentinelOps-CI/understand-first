// Understand-First C# AST worker (Wave 24).
//
// Parse-only via Microsoft.CodeAnalysis.CSharp (not typechecked / not MSBuild).
// Complexity (ast-cyclomatic): 1 + If/For/ForEach/While/Do/Case/Catch/
//   ConditionalExpression/&&/||; nested local function bodies excluded.
//
// stdin JSON: { "root": "<abs>", "files": ["rel.cs", ...] }
// stdout JSON: { "ok": true, "files": [...], "complexity_formula": "..." }

using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

const string ComplexityFormula =
    "1 + If/For/ForEach/While/Do/Case/Catch/Conditional/&&/||; nested local funcs excluded";

var raw = Console.In.ReadToEnd();
Request? req;
try
{
    req = JsonSerializer.Deserialize<Request>(raw);
}
catch (Exception ex)
{
    EmitErr($"invalid JSON: {ex.Message}");
    return 1;
}

if (req is null || string.IsNullOrWhiteSpace(req.Root))
{
    EmitErr("missing root");
    return 1;
}

var root = req.Root;
var filesOut = new List<FileEntry>();
foreach (var relRaw in req.Files ?? [])
{
    var rel = relRaw.Replace('\\', '/');
    if (!rel.EndsWith(".cs", StringComparison.OrdinalIgnoreCase))
        continue;

    string abs;
    if (Path.IsPathRooted(relRaw))
        abs = relRaw;
    else
        abs = Path.Combine(root, relRaw);

    try
    {
        filesOut.Add(ParseFile(abs, rel));
    }
    catch
    {
        filesOut.Add(new FileEntry
        {
            File = rel,
            Namespace = "",
            Functions = new Dictionary<string, FuncMeta>(),
        });
    }
}

var resp = new Response
{
    Ok = true,
    ComplexityFormula = ComplexityFormula,
    Files = filesOut,
};
Console.Write(JsonSerializer.Serialize(resp, JsonOpts()));
return 0;

static void EmitErr(string msg)
{
    Console.Write(JsonSerializer.Serialize(new Response { Ok = false, Error = msg }, JsonOpts()));
}

static JsonSerializerOptions JsonOpts() => new()
{
    PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
};

static FileEntry ParseFile(string abs, string display)
{
    var src = File.ReadAllText(abs);
    var tree = CSharpSyntaxTree.ParseText(src, path: abs);
    var root = tree.GetCompilationUnitRoot();

    var ns = "";
    var fileScoped = root.Members.OfType<FileScopedNamespaceDeclarationSyntax>().FirstOrDefault();
    if (fileScoped is not null)
        ns = fileScoped.Name.ToString();
    else
    {
        var blockNs = root.DescendantNodes().OfType<NamespaceDeclarationSyntax>().FirstOrDefault();
        if (blockNs is not null)
            ns = blockNs.Name.ToString();
    }

    var funcs = new Dictionary<string, FuncMeta>(StringComparer.Ordinal);
    foreach (var type in root.DescendantNodes().OfType<TypeDeclarationSyntax>())
    {
        // Skip nested types for qname simplicity (outermost type name only when nested).
        var typeName = type.Identifier.ValueText;
        if (string.IsNullOrEmpty(typeName))
            continue;

        foreach (var member in type.Members)
        {
            if (member is MethodDeclarationSyntax method)
            {
                var simple = method.Identifier.ValueText;
                if (string.IsNullOrEmpty(simple) || IsKeywordCallee(simple))
                    continue;
                var local = $"{typeName}.{simple}";
                var line = method.Identifier.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
                funcs[local] = ExtractMethod(display, simple, method, line);
            }
            else if (member is ConstructorDeclarationSyntax ctor)
            {
                var line = ctor.Identifier.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
                var local = $"{typeName}.<init>";
                funcs[local] = ExtractCtor(display, ctor, line);
            }
        }
    }

    return new FileEntry
    {
        File = display.Replace('\\', '/'),
        Namespace = ns,
        Functions = funcs,
    };
}

static FuncMeta ExtractMethod(string file, string simple, MethodDeclarationSyntax method, int line)
{
    var (calls, complexity) = WalkBody(method.Body, method.ExpressionBody);
    return new FuncMeta
    {
        SimpleName = simple,
        File = file.Replace('\\', '/'),
        Calls = calls,
        Callers = [],
        Complexity = complexity,
        Line = line <= 0 ? 1 : line,
        Language = "csharp",
    };
}

static FuncMeta ExtractCtor(string file, ConstructorDeclarationSyntax ctor, int line)
{
    var (calls, complexity) = WalkBody(ctor.Body, ctor.ExpressionBody);
    return new FuncMeta
    {
        SimpleName = "<init>",
        File = file.Replace('\\', '/'),
        Calls = calls,
        Callers = [],
        Complexity = complexity,
        Line = line <= 0 ? 1 : line,
        Language = "csharp",
    };
}

static (List<string> calls, int complexity) WalkBody(
    BlockSyntax? body,
    ArrowExpressionClauseSyntax? expressionBody)
{
    var visitor = new BodyVisitor();
    if (body is not null)
        visitor.Visit(body);
    else if (expressionBody is not null)
        visitor.Visit(expressionBody);
    return (visitor.Calls.ToList(), visitor.Complexity);
}

sealed class BodyVisitor : CSharpSyntaxWalker
{
    public SortedSet<string> Calls { get; } = new(StringComparer.Ordinal);
    public int Complexity { get; private set; } = 1;

    public override void VisitLocalFunctionStatement(LocalFunctionStatementSyntax node)
    {
        // Nested local functions: do not descend (would double-count).
    }

    public override void VisitAnonymousMethodExpression(AnonymousMethodExpressionSyntax node)
    {
        // Exclude anonymous method bodies from enclosing CC / calls.
    }

    public override void VisitSimpleLambdaExpression(SimpleLambdaExpressionSyntax node)
    {
        // Exclude lambda bodies.
    }

    public override void VisitParenthesizedLambdaExpression(ParenthesizedLambdaExpressionSyntax node)
    {
        // Exclude lambda bodies.
    }

    public override void VisitIfStatement(IfStatementSyntax node)
    {
        Complexity++;
        base.VisitIfStatement(node);
    }

    public override void VisitForStatement(ForStatementSyntax node)
    {
        Complexity++;
        base.VisitForStatement(node);
    }

    public override void VisitForEachStatement(ForEachStatementSyntax node)
    {
        Complexity++;
        base.VisitForEachStatement(node);
    }

    public override void VisitForEachVariableStatement(ForEachVariableStatementSyntax node)
    {
        Complexity++;
        base.VisitForEachVariableStatement(node);
    }

    public override void VisitWhileStatement(WhileStatementSyntax node)
    {
        Complexity++;
        base.VisitWhileStatement(node);
    }

    public override void VisitDoStatement(DoStatementSyntax node)
    {
        Complexity++;
        base.VisitDoStatement(node);
    }

    public override void VisitCatchClause(CatchClauseSyntax node)
    {
        Complexity++;
        base.VisitCatchClause(node);
    }

    public override void VisitSwitchSection(SwitchSectionSyntax node)
    {
        // Count each case/default label group once via CaseSwitchLabel / DefaultSwitchLabel.
        var hasCase = node.Labels.Any(l => l is CaseSwitchLabelSyntax or CasePatternSwitchLabelSyntax);
        var hasDefault = node.Labels.Any(l => l is DefaultSwitchLabelSyntax);
        if (hasCase || hasDefault)
            Complexity++;
        base.VisitSwitchSection(node);
    }

    public override void VisitConditionalExpression(ConditionalExpressionSyntax node)
    {
        Complexity++;
        base.VisitConditionalExpression(node);
    }

    public override void VisitBinaryExpression(BinaryExpressionSyntax node)
    {
        if (node.IsKind(SyntaxKind.LogicalAndExpression) || node.IsKind(SyntaxKind.LogicalOrExpression))
            Complexity++;
        base.VisitBinaryExpression(node);
    }

    public override void VisitInvocationExpression(InvocationExpressionSyntax node)
    {
        var name = InvocationName(node.Expression);
        if (name is not null && !IsKeywordCallee(name))
            Calls.Add(name);
        base.VisitInvocationExpression(node);
    }

    static string? InvocationName(ExpressionSyntax expr) =>
        expr switch
        {
            IdentifierNameSyntax id => id.Identifier.ValueText,
            MemberAccessExpressionSyntax ma => ma.Name.Identifier.ValueText,
            GenericNameSyntax g => g.Identifier.ValueText,
            MemberBindingExpressionSyntax mb => mb.Name.Identifier.ValueText,
            ParenthesizedExpressionSyntax p => InvocationName(p.Expression),
            _ => null,
        };
}

static bool IsKeywordCallee(string name) =>
    name is "if" or "for" or "foreach" or "while" or "switch" or "case" or "catch"
        or "return" or "new" or "throw" or "nameof" or "typeof" or "sizeof" or "default"
        or "checked" or "unchecked" or "await" or "base" or "this";

sealed class Request
{
    [JsonPropertyName("root")]
    public string Root { get; set; } = "";

    [JsonPropertyName("files")]
    public List<string>? Files { get; set; }
}

sealed class FuncMeta
{
    [JsonPropertyName("simple_name")]
    public string SimpleName { get; set; } = "";

    [JsonPropertyName("file")]
    public string File { get; set; } = "";

    [JsonPropertyName("calls")]
    public List<string> Calls { get; set; } = [];

    [JsonPropertyName("callers")]
    public List<string> Callers { get; set; } = [];

    [JsonPropertyName("complexity")]
    public int Complexity { get; set; }

    [JsonPropertyName("line")]
    public int Line { get; set; }

    [JsonPropertyName("language")]
    public string Language { get; set; } = "csharp";
}

sealed class FileEntry
{
    [JsonPropertyName("file")]
    public string File { get; set; } = "";

    [JsonPropertyName("namespace")]
    public string Namespace { get; set; } = "";

    [JsonPropertyName("functions")]
    public Dictionary<string, FuncMeta> Functions { get; set; } = new();
}

sealed class Response
{
    [JsonPropertyName("ok")]
    public bool Ok { get; set; }

    [JsonPropertyName("error")]
    public string? Error { get; set; }

    [JsonPropertyName("complexity_formula")]
    public string? ComplexityFormula { get; set; }

    [JsonPropertyName("files")]
    public List<FileEntry>? Files { get; set; }
}
