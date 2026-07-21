/** TypeScript with interfaces — types stripped best-effort, not interpreted. */
export interface Person {
  name: string;
  age: number;
}

export type Id = string | number;

export function summarize(p: Person): string {
  return joinName(p.name, p.age);
}

export function joinName(name: string, age: number): string {
  if (age < 0) {
    return name;
  }
  return `${name}:${age}`;
}
