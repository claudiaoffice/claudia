// pdf.js (Mozilla's PDF reader, not our code) as an independent check of the PDFs the writer makes.
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { pathToFileURL } from 'node:url'

const require = createRequire(import.meta.url)
const root = dirname(require.resolve('pdfjs-dist/package.json'))
// pdf.js warns about optional canvas packages it does not need for reading text; keep the test output clean
const quiet = { verbosity: 0 }

export interface PdfText {
  pages: { width: number; height: number; items: { str: string; x: number; y: number; w: number; size: number }[] }[]
}

export async function readPdf(bytes: Uint8Array): Promise<PdfText> {
  const pdfjs = await import(pathToFileURL(join(root, 'legacy', 'build', 'pdf.mjs')).href)
  const doc = await pdfjs.getDocument({ data: bytes.slice(), useSystemFonts: false, disableFontFace: true, ...quiet }).promise
  const out: PdfText = { pages: [] }
  for (let p = 1; p <= doc.numPages; p++) {
    const page = await doc.getPage(p)
    const [x0, y0, x1, y1] = page.view
    const tc = await page.getTextContent()
    out.pages.push({
      width: x1 - x0,
      height: y1 - y0,
      items: tc.items
        .filter((i: { str: string }) => i.str !== '')
        .map((i: { str: string; transform: number[]; width: number }) => ({ str: i.str, x: i.transform[4]!, y: i.transform[5]!, w: i.width, size: i.transform[0]! })),
    })
  }
  return out
}
