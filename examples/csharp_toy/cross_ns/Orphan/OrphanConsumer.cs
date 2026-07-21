namespace Toy.Orphan;

using Toy.Lib;

/** Orphan project: using Toy.Lib but no ProjectReference — must not invent. */
public static class OrphanConsumer
{
    public static string Run()
    {
        return UniqueOp();
    }
}
