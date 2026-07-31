/**
 * Run async work over items with a fixed concurrency limit.
 * Useful for image preview loads so we don't flood the network.
 */
export async function asyncPool<T>(
  items: readonly T[],
  concurrency: number,
  worker: (item: T, index: number) => Promise<void>,
): Promise<void> {
  if (!items.length) return
  const limit = Math.max(1, Math.min(concurrency, items.length))
  let next = 0

  async function run(): Promise<void> {
    while (next < items.length) {
      const index = next++
      await worker(items[index], index)
    }
  }

  await Promise.all(Array.from({ length: limit }, () => run()))
}
