// Provides layout class decisions for personal info preview sections.
import type { CSSProperties } from 'react'

export interface FormalPersonalInfoLayout {
  containerClassName: string
  headerClassName: string
  textClassName: string
  contactClassName: string
  photoWrapClassName: string
}

export interface CenteredPersonalInfoLayout {
  containerClassName: string
  headerClassName: string
  headerStyle: CSSProperties
  textClassName: string
  contactClassName: string
  photoWrapClassName: string
}

export interface EmeraldPersonalInfoLayout {
  containerClassName: string
  nameBlockClassName: string
  textClassName: string
  contactClassName: string
  photoWrapClassName: string
}

const PHOTO_SAFE_PADDING_CLASS = 'pr-[96px]'
const PHOTO_SAFE_X_PADDING_CLASS = 'px-[96px]'

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

// Returns centered template classes that keep the profile photo out of document flow.
export function getCenteredPersonalInfoLayout(hasPhoto: boolean): CenteredPersonalInfoLayout {
  const safePaddingClass = hasPhoto ? PHOTO_SAFE_X_PADDING_CLASS : ''
  return {
    containerClassName: 'relative',
    headerClassName: 'relative text-center',
    headerStyle: {},
    textClassName: safePaddingClass,
    contactClassName: safePaddingClass,
    photoWrapClassName: hasPhoto ? 'absolute right-0 top-0' : '',
  }
}

// Returns emerald template classes that keep the profile photo out of document flow.
export function getEmeraldPersonalInfoLayout(hasPhoto: boolean): EmeraldPersonalInfoLayout {
  const safePaddingClass = hasPhoto ? PHOTO_SAFE_PADDING_CLASS : ''
  return {
    containerClassName: 'resume-emerald-personal relative',
    nameBlockClassName: 'resume-emerald-name-block relative',
    textClassName: ['min-w-0', safePaddingClass].filter(Boolean).join(' '),
    contactClassName: safePaddingClass,
    photoWrapClassName: hasPhoto ? 'absolute right-0 top-4' : '',
  }
}
