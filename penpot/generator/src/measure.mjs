// Measures text in a real browser with the fonts claudia ships (the web app itself loads them), so line heights,
// widths and line breaks in the Penpot file are the ones the running app has.
import { chromium } from 'playwright-core'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'

const CHROME = process.env.CHROME_PATH ?? '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome'

/** CSS for a font spec: { family, size, weight, style, ls (px), transform, lh (number factor | 'normal') }. */
export function cssOf(f) {
  return [
    `font-family:'${f.family}'`,
    `font-size:${f.size}px`,
    `font-weight:${f.weight ?? 400}`,
    `font-style:${f.style ?? 'normal'}`,
    `letter-spacing:${f.ls ?? 0}px`,
    `text-transform:${f.transform ?? 'none'}`,
    `line-height:${f.lh === 'normal' || f.lh === undefined ? 'normal' : f.lh}`,
  ].join(';')
}

export async function createMeasurer({ url, cacheFile }) {
  const cache = cacheFile && existsSync(cacheFile) ? JSON.parse(readFileSync(cacheFile, 'utf8')) : {}
  let browser
  let page
  const open = async () => {
    if (page) return
    browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] })
    page = await browser.newPage()
    await page.goto(url)
    await page.waitForTimeout(800)
  }

  /** The lines a text breaks into at `width` (null: one line), with their widths and the line height. */
  async function text(font, content, width = null) {
    const key = JSON.stringify([font, content, width])
    if (cache[key]) return cache[key]
    await open()
    const res = await page.evaluate(
      async ([css, fontSpec, content, width]) => {
        await document.fonts.load(`${fontSpec.style ?? 'normal'} ${fontSpec.weight ?? 400} ${fontSpec.size}px "${fontSpec.family}"`, content)
        const el = document.createElement('div')
        el.setAttribute('style', `position:absolute;left:0;top:0;visibility:hidden;margin:0;padding:0;${css};${width === null ? 'white-space:nowrap' : `width:${width}px;white-space:normal;overflow-wrap:break-word`}`)
        el.textContent = content
        document.body.appendChild(el)
        const node = el.firstChild
        const lines = []
        const range = document.createRange()
        let cur = null
        for (let i = 0; i < content.length; i++) {
          range.setStart(node, i)
          range.setEnd(node, i + 1)
          const r = range.getBoundingClientRect()
          if (r.width === 0 && /\s/.test(content[i])) {
            if (cur) cur.text += content[i]
            continue
          }
          if (!cur || r.top > cur.top + cur.h / 2) {
            cur = { text: '', top: r.top, h: r.height, x: r.left, right: r.right }
            lines.push(cur)
          }
          cur.text += content[i]
          cur.right = Math.max(cur.right, r.right)
        }
        const total = el.getBoundingClientRect()
        const out = {
          width: total.width,
          height: total.height,
          lines: lines.map((l) => ({ text: l.text.replace(/\s+$/, ''), x: l.x, w: l.right - l.x })),
        }
        out.lineHeight = lines.length ? total.height / lines.length : total.height
        el.remove()
        return out
      },
      [cssOf(font), font, content, width],
    )
    cache[key] = res
    return res
  }

  /** The line height in px of a font spec with `line-height: normal` (or a factor). */
  async function lineHeight(font) {
    if (typeof font.lh === 'number') return font.lh * font.size
    return (await text({ ...font, lh: 'normal' }, 'Hg')).lineHeight
  }

  return {
    text,
    lineHeight,
    async close() {
      if (cacheFile) writeFileSync(cacheFile, JSON.stringify(cache))
      await browser?.close()
    },
  }
}
