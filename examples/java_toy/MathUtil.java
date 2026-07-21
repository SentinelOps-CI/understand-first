package toy;

/** Small Java fixture for Understand-First Wave 20. */
public class MathUtil {
  public static int add(int a, int b) {
    return a + b;
  }

  public static int compute(int x, int y) {
    return add(x, y);
  }

  public static String classify(int n) {
    if (n < 0) {
      return "neg";
    }
    for (int i = 0; i < n; i++) {
      if (i > 10 && i < 20) {
        return "mid";
      }
    }
    switch (n) {
      case 0:
        return "zero";
      default:
        return "other";
    }
  }
}
