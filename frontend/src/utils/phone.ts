export const PHONE_INPUT_MESSAGE = '手机号必须为11位数字且以1开头'

const PHONE_PATTERN = /^1\d{10}$/

export function sanitizePhoneInput(value: unknown): string {
  return String(value ?? '')
    .replace(/\D/g, '')
    .slice(0, 11)
}

export function isValidOptionalPhone(value: unknown): boolean {
  const phone = String(value ?? '')
  return phone === '' || PHONE_PATTERN.test(phone)
}

export function isValidRequiredPhone(value: unknown): boolean {
  return PHONE_PATTERN.test(String(value ?? ''))
}

export function validateRequiredPhone(
  _rule: unknown,
  value: unknown,
  callback: (error?: Error) => void,
): void {
  callback(isValidRequiredPhone(value) ? undefined : new Error(PHONE_INPUT_MESSAGE))
}

export function assertValidOptionalPhone(value: unknown): void {
  if (!isValidOptionalPhone(value)) {
    throw new Error(PHONE_INPUT_MESSAGE)
  }
}

export function validateOptionalPhone(
  _rule: unknown,
  value: unknown,
  callback: (error?: Error) => void,
): void {
  callback(isValidOptionalPhone(value) ? undefined : new Error(PHONE_INPUT_MESSAGE))
}
