namespace Toy;

/** Small C# fixture for Understand-First Wave 24. */
public static class MathUtil
{
    public static int Add(int a, int b)
    {
        return a + b;
    }

    public static int Compute(int x, int y)
    {
        return Add(x, y);
    }

    public static string Classify(int n)
    {
        if (n < 0)
        {
            return "neg";
        }
        for (int i = 0; i < n; i++)
        {
            if (i > 10 && i < 20)
            {
                return "mid";
            }
        }
        switch (n)
        {
            case 0:
                return "zero";
            default:
                return "other";
        }
    }
}
