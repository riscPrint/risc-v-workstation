export function candidates(value: unknown): string[] {
  return Array.isArray(value) ? [...new Set(value.filter((v): v is string => typeof v === 'string' && !!v))] : [];
}
export function dependencyArgs(kind: 'drivers' | 'loads', db: string, signal: string): string[] {
  return ['query', kind, ...(db ? ['--db', db] : []), '--json', '--', signal];
}
