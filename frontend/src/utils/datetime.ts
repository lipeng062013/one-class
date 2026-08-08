function pad(value: number): string {
  return String(value).padStart(2, '0')
}

/**
 * 业务时间按本地墙钟提交，不附加 UTC 标记。
 * 后端统一按中国标准时间的墙钟值存储，不能使用 toISOString() 额外减 8 小时。
 */
export function toBusinessDateTimeIso(
  value: Date | string | null | undefined,
): string | null {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return [
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`,
  ].join('T')
}
