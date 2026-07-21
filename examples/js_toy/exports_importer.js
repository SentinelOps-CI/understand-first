/** Imports via package.json exports subpath ./mapped → exports_target.js */
import { mappedUtil } from "./mapped";

export function runMapped(x) {
  return mappedUtil(x);
}
