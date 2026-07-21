namespace Toy;

/** Calls HelperFn() in the same namespace (cross-file). */
public static class Importer
{
    public static string RunShared()
    {
        return HelperFn();
    }
}
