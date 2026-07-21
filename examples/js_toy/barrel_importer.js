/** Imports through a re-export barrel (Wave 21). */
import { barrelUtil } from "./barrel/index.js";

export function runBarrel(x) {
  return barrelUtil(x);
}
