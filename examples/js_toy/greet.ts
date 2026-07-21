/** TypeScript best-effort fixture — types are not interpreted by the analyzer. */
export function greet(name: string): string {
  return format(name);
}

export function format(name: string): string {
  return `hello ${name}`;
}
