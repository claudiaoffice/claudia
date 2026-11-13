/**
 * Sine and cosine of whole degrees as millionths, from a table instead of `Math.sin`, whose last digit may differ
 * between JavaScript engines. Used to rotate objects; a rotation is rounded to a whole degree first.
 *
 * @module
 */
const SIN_MILLIONTHS: readonly number[] = [
  0, 17452, 34899, 52336, 69756, 87156, 104528, 121869, 139173, 156434, 173648, 190809, 207912, 224951, 241922,
  258819, 275637, 292372, 309017, 325568, 342020, 358368, 374607, 390731, 406737, 422618, 438371, 453990, 469472,
  484810, 500000, 515038, 529919, 544639, 559193, 573576, 587785, 601815, 615661, 629320, 642788, 656059, 669131,
  681998, 694658, 707107, 719340, 731354, 743145, 754710, 766044, 777146, 788011, 798636, 809017, 819152, 829038,
  838671, 848048, 857167, 866025, 874620, 882948, 891007, 898794, 906308, 913545, 920505, 927184, 933580, 939693,
  945519, 951057, 956305, 961262, 965926, 970296, 974370, 978148, 981627, 984808, 987688, 990268, 992546, 994522,
  996195, 997564, 998630, 999391, 999848, 1000000,
]

/** sin(deg) × 10^6, exact for whole degrees (rounded). */
export function sinMillionths(deg: number): number {
  const d = ((Math.round(deg) % 360) + 360) % 360
  if (d <= 90) return SIN_MILLIONTHS[d]!
  if (d <= 180) return SIN_MILLIONTHS[180 - d]!
  if (d <= 270) return -SIN_MILLIONTHS[d - 180]!
  return -SIN_MILLIONTHS[360 - d]!
}

/** cos(deg) × 10^6. */
export const cosMillionths = (deg: number): number => sinMillionths(Math.round(deg) + 90)
