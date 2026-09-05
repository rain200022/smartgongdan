// Drafts live only in this tab's memory. Never persist ticket contents or credentials.
const drafts = new Map<string, string>()

function draftKey(userId: number, key: string): string {
  return `${userId}:${key}`
}

export function readDraft<T>(userId: number, key: string): T | null {
  const value = drafts.get(draftKey(userId, key))
  return value ? (JSON.parse(value) as T) : null
}

export function saveDraft(userId: number, key: string, value: object): void {
  drafts.set(draftKey(userId, key), JSON.stringify(value))
}

export function removeDraft(userId: number, key: string): void {
  drafts.delete(draftKey(userId, key))
}

export function clearDrafts(): void {
  drafts.clear()
}
