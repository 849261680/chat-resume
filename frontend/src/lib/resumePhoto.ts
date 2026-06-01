// 用于提供简历照片地址的规范化能力。

const IMAGE_DATA_URL_PATTERN = /^data:image\/(?:png|jpe?g|webp|gif);base64,/i

// 用于规范化简历照片地址。
export function normalizeResumePhotoUrl(value: unknown): string {
  if (typeof value !== 'string') {
    return ''
  }

  const photoUrl = value.trim()
  if (!photoUrl) {
    return ''
  }

  if (IMAGE_DATA_URL_PATTERN.test(photoUrl)) {
    return photoUrl
  }

  try {
    const parsedUrl = new URL(photoUrl)
    if (parsedUrl.protocol === 'http:' || parsedUrl.protocol === 'https:') {
      return parsedUrl.href
    }
  } catch {
    return ''
  }

  return ''
}
