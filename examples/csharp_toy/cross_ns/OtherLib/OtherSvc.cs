namespace Toy.Other;

/** Same simple name Clash — ambiguous when both namespaces are imported + visible. */
public static class OtherSvc
{
    public static string Clash()
    {
        return "other-clash";
    }
}
