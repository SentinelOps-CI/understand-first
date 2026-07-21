package toy;

/** Instance methods for Class.method qnames. */
public class Calc {
  public int scale(int v) {
    return MathUtil.add(v, 0);
  }

  public int run(int a, int b) {
    return scale(MathUtil.compute(a, b));
  }
}
