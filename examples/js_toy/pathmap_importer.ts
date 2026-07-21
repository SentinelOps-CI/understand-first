/** Imports via nearest tsconfig paths @lib/* → lib/* (Wave 29). */
import { pathMappedUtil } from "@lib/pathmapped_util";

export function runPathMapped(x: number): number {
  return pathMappedUtil(x);
}
