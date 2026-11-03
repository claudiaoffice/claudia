// Colours offered by the colour picker: the suite's own (design system), then greys and a few plain ones for text.
export interface Swatch {
  name: string
  value: string
}

export const SWATCHES: Swatch[] = [
  { name: 'Ink', value: '#1F1A33' },
  { name: 'Iris', value: '#5B4BC4' },
  { name: 'Rose', value: '#D6477A' },
  { name: 'Teal', value: '#13917F' },
  { name: 'Apricot', value: '#F2A057' },
  { name: 'Mist', value: '#E7E1F4' },
  { name: 'Paper', value: '#F7F3EC' },
  { name: 'White', value: '#FFFFFF' },
  { name: 'Black', value: '#000000' },
  { name: 'Grey 700', value: '#4A4560' },
  { name: 'Grey 500', value: '#7C7893' },
  { name: 'Grey 300', value: '#C9C6D6' },
  { name: 'Red', value: '#C0392B' },
  { name: 'Orange', value: '#D9822B' },
  { name: 'Green', value: '#2E8B57' },
  { name: 'Blue', value: '#2563EB' },
]
