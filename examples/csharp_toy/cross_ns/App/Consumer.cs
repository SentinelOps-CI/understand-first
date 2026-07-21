namespace Toy.App;

using Toy.Lib;
using Toy.Other;
using LibAlias = Toy.Lib.UniqueSvc;

/** App project references Lib only — OtherLib is not project-visible. */
public static class Consumer
{
    public static string RunUnique()
    {
        return UniqueOp();
    }

    public static string RunTyped()
    {
        return UniqueSvc.UniqueOp();
    }

    public static string RunAliased()
    {
        return LibAlias.UniqueOp();
    }

    // Clash exists in Toy.Lib (visible) and Toy.Other (using present, not project-visible).
    // With project graph: only Lib Clash is visible → unique.
    public static string RunClashVisible()
    {
        return Clash();
    }
}
