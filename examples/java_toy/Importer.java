package toy;

/** Calls Helper.helper() in the same package (cross-file). */
public class Importer {
  public static String runShared() {
    return helper();
  }
}
