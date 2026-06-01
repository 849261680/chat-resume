// Provides layout class decisions for personal info preview sections.

export interface FormalPersonalInfoLayout {
  containerClassName: string
  headerClassName: string
  textClassName: string
  contactClassName: string
  photoWrapClassName: string
}

const PHOTO_SAFE_PADDING_CLASS = 'pr-[96px]'

// Returns formal template classes that keep the profile photo out of document flow.
export function getFormalPersonalInfoLayout(hasPhoto: boolean): FormalPersonalInfoLayout {
  const safePaddingClass = hasPhoto ? PHOTO_SAFE_PADDING_CLASS : ''
  return {
    containerClassName: hasPhoto ? 'resume-formal-personal relative' : 'resume-formal-personal',
    headerClassName: 'relative',
    textClassName: ['min-w-0', safePaddingClass].filter(Boolean).join(' '),
    contactClassName: safePaddingClass,
    photoWrapClassName: hasPhoto ? 'absolute right-0 top-0' : '',
  }
}
