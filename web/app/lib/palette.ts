// Colours offered by the colour picker: the suite's own (design system), then greys and a few plain ones for text.

import { translate as t } from './i18n'

export interface Swatch {
  name: string
  value: string
}

export const SWATCHES: Swatch[] = [
  { get name() { return t('Ink') }, value: '#1F1A33' },
  { get name() { return t('Iris') }, value: '#5B4BC4' },
  { get name() { return t('Rose') }, value: '#D6477A' },
  { get name() { return t('Teal') }, value: '#13917F' },
  { get name() { return t('Apricot') }, value: '#F2A057' },
  { get name() { return t('Mist') }, value: '#E7E1F4' },
  { get name() { return t('Paper') }, value: '#F7F3EC' },
  { get name() { return t('White') }, value: '#FFFFFF' },
  { get name() { return t('Black') }, value: '#000000' },
  { name: 'Grey 700', value: '#4A4560' },
  { name: 'Grey 500', value: '#7C7893' },
  { name: 'Grey 300', value: '#C9C6D6' },
  { get name() { return t('Red') }, value: '#C0392B' },
  { get name() { return t('Orange') }, value: '#D9822B' },
  { get name() { return t('Green') }, value: '#2E8B57' },
  { get name() { return t('Blue') }, value: '#2563EB' },
]
