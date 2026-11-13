// A font world for tests: the starter set registered in a FontSet, and a resolver over it as a server would list it.
import { FontSet } from '../src/fonts/fontset'
import { type Catalogue, FontResolver } from '../src/fonts/resolve'
import { readSfnt } from '../src/fonts/sfnt'
import { fixture, lock } from './fonts'
import { harfbuzz, sha256 } from './helpers'

export async function world(): Promise<{ fonts: FontSet; resolver: FontResolver; catalogue: Catalogue }> {
  const fonts = new FontSet(await harfbuzz())
  const catalogue: Catalogue = { fonts: [], substitutions: { Arial: 'Liberation Sans', Calibri: 'Carlito', Cambria: 'Caladea' } }
  for (const c of lock()) {
    for (const f of c.files) {
      if (!f.name.endsWith('.ttf')) continue
      const bytes = fixture(f.name)
      const info = readSfnt(bytes)
      const hash = sha256(bytes)
      fonts.add(hash, bytes)
      const italic = /Italic/.test(f.name)
      catalogue.fonts.push({ family: c.name, style: italic ? 'Italic' : 'Regular', weight: info.weight, italic, sha256: hash, axes: info.axes, outlines: info.outlines })
    }
  }
  return { fonts, resolver: new FontResolver(catalogue), catalogue }
}
