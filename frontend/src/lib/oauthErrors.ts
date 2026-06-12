// 用于提供 lib/oauthErrors.ts 模块。

const OAUTH_ERROR_KEYS = new Set([
  'cancelled',
  'invalid_state',
  'google_exchange_failed',
  'unverified_email',
  'account_conflict',
  'provider_unavailable',
  'config_missing',
  'unknown',
])

// 用于获取OAuth错误键。
export function getOAuthErrorKey(errorCode: string | null) {
  if (!errorCode) return null
  return OAUTH_ERROR_KEYS.has(errorCode) ? errorCode : 'unknown'
}
