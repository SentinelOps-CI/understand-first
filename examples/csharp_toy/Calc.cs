namespace Toy;

/** Instance methods for Class.method qnames. */
public class Calc
{
    public int Scale(int v)
    {
        return MathUtil.Add(v, 0);
    }

    public int Run(int a, int b)
    {
        return Scale(MathUtil.Compute(a, b));
    }
}
