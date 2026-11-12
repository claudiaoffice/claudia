/**
 * HarfBuzz as WebAssembly: shaping (the engine Chrome, Firefox and Android use) and subsetting with instancing of
 * variable fonts (for the PDF). The library talks to the two `.wasm` files of harfbuzzjs directly, without their
 * JavaScript glue, so that the caller can hand in exactly the bytes it has checked against {@link HARFBUZZ_PIN}: in
 * Node read from disk, in a browser fetched from the server.
 *
 * Everything here works in font units at the font's own scale (units per em), so all results are integers.
 *
 * @module
 */

/** The WebAssembly files, by SHA-256 of their bytes. A layout result names the build it was shaped with. */
export const HARFBUZZ_PIN = {
  package: 'harfbuzzjs',
  version: '1.6.4',
  shaping: { file: 'harfbuzz.wasm', sha256: '6eeed8e1bc9ad7773038e48ff8f9e07e0ad228572c594b45e5357e9c2f7a0b2e' },
  subset: { file: 'harfbuzz-subset.wasm', sha256: '62415fe6bad92ef16f3e5d2dbed6c66a4adec7f5a59c6d27084811c92cce1ba5' },
} as const

/** The id of the shaping engine as recorded in layout results: package, version and the first hex digits of the hash. */
export const SHAPER_ID = `${HARFBUZZ_PIN.package}-${HARFBUZZ_PIN.version}+${HARFBUZZ_PIN.shaping.sha256.slice(0, 8)}`

/** The bytes of both WebAssembly files. */
export interface HarfBuzzWasm {
  shaping: Uint8Array
  subset: Uint8Array
}

/** A function that gives the SHA-256 of some bytes as lower-case hex (the platform's crypto). */
export type Sha256 = (bytes: Uint8Array) => Promise<string> | string

/** Axis tag → value, e.g. `{ wght: 500 }`. */
export type Variations = Readonly<Record<string, number>>

/** One shaped glyph, in font units. `cluster` is the UTF-16 index in the shaped text where its characters start. */
export interface Glyph {
  gid: number
  cluster: number
  xAdvance: number
  yAdvance: number
  xOffset: number
  yOffset: number
}

/** Vertical extents of a font (with its variations applied), in font units; `descender` is negative. */
export interface Extents {
  ascender: number
  descender: number
  lineGap: number
}

/** A font opened for shaping. Close it with {@link HarfBuzz.close} when it is no longer needed. */
export interface HbFont {
  readonly upem: number
  /** internal */
  readonly ptr: number
}

/** Shaping options. Defaults: script, language and direction guessed from the text, HarfBuzz's default features. */
export interface ShapeOptions {
  /** OpenType feature strings as HarfBuzz reads them: `"kern=0"`, `"-liga"`, `"tnum"`. */
  features?: readonly string[]
  /** BCP 47 language tag, e.g. `de` or `en-US`. */
  language?: string
}

type Fn = (...args: number[]) => number

// The part of the WebAssembly JavaScript API used here. It is a standard global in every engine the library runs in,
// but its types live in lib.dom and @types/node, which the library does not load; so it is reached through
// `globalThis` with these local types, which cannot clash with either.
interface WasmMemory {
  readonly buffer: ArrayBuffer
  grow(pages: number): number
}
interface WasmApi {
  instantiate(bytes: Uint8Array, imports: object): Promise<{ instance: { exports: Record<string, unknown> } }>
}
const wasmApi = (): WasmApi => {
  const api = (globalThis as unknown as { WebAssembly?: WasmApi }).WebAssembly
  if (!api) throw new Error('this JavaScript engine has no WebAssembly')
  return api
}

function tagOf(s: string): number {
  return (((s.charCodeAt(0) & 255) << 24) | ((s.charCodeAt(1) & 255) << 16) | ((s.charCodeAt(2) & 255) << 8) | (s.charCodeAt(3) & 255)) >>> 0
}

/** A WebAssembly file that does not match its pin. */
export class WasmMismatch extends Error {}

async function check(bytes: Uint8Array, want: string, name: string, sha256?: Sha256): Promise<void> {
  if (!sha256) return
  const got = await sha256(bytes)
  if (got !== want) throw new WasmMismatch(`${name} has SHA-256 ${got}, expected ${want}`)
}

class Heap {
  constructor(private readonly memory: WasmMemory) {}
  get u8(): Uint8Array {
    return new Uint8Array(this.memory.buffer)
  }
  get view(): DataView {
    return new DataView(this.memory.buffer)
  }
}

/**
 * The two HarfBuzz modules, loaded. Not safe to share between threads; one per page or worker.
 */
export class HarfBuzz {
  private readonly blobs = new Map<number, { blob: number; face: number; data: number }>()

  private constructor(
    private readonly hb: Record<string, Fn>,
    private readonly heap: Heap,
    private readonly sub: Record<string, Fn>,
    private readonly subHeap: Heap,
  ) {}

  /**
   * Instantiate both modules. With `sha256`, the bytes are checked against {@link HARFBUZZ_PIN} first and a
   * {@link WasmMismatch} is thrown if either differs.
   */
  static async load(wasm: HarfBuzzWasm, sha256?: Sha256): Promise<HarfBuzz> {
    await check(wasm.shaping, HARFBUZZ_PIN.shaping.sha256, HARFBUZZ_PIN.shaping.file, sha256)
    await check(wasm.subset, HARFBUZZ_PIN.subset.sha256, HARFBUZZ_PIN.subset.file, sha256)
    let memory: WasmMemory | undefined
    const fail = (what: string) => () => {
      throw new Error(`harfbuzz: ${what}`)
    }
    const env = {
      _emscripten_runtime_keepalive_clear: () => {},
      _abort_js: fail('abort'),
      _setitimer_js: () => 0,
      emscripten_resize_heap: (requested: number) => {
        if (!memory) return 0
        const have = memory.buffer.byteLength
        const want = Math.max(requested >>> 0, have * 2)
        try {
          memory.grow(Math.ceil((want - have) / 65536))
          return 1
        } catch {
          return 0
        }
      },
    }
    const shaping = await wasmApi().instantiate(wasm.shaping, { env, wasi_snapshot_preview1: { proc_exit: fail('exit') } })
    const hb = shaping.instance.exports as unknown as Record<string, Fn> & { memory: WasmMemory }
    memory = hb.memory
    hb.__wasm_call_ctors?.()
    const subset = await wasmApi().instantiate(wasm.subset, {})
    const sub = subset.instance.exports as unknown as Record<string, Fn> & { memory: WasmMemory }
    sub._initialize?.()
    return new HarfBuzz(hb, new Heap(hb.memory), sub, new Heap(sub.memory))
  }

  /** Open a font file for shaping, at the given axis location (only for a variable font). */
  open(bytes: Uint8Array, variations: Variations = {}): HbFont {
    const { hb } = this
    const data = hb.malloc!(bytes.length)
    this.heap.u8.set(bytes, data)
    const blob = hb.hb_blob_create!(data, bytes.length, 1 /* READONLY */, 0, 0)
    const face = hb.hb_face_create!(blob, 0)
    const font = hb.hb_font_create!(face)
    const entries = Object.entries(variations).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    if (entries.length) {
      const ptr = hb.malloc!(8 * entries.length)
      const view = this.heap.view
      entries.forEach(([t, v], i) => {
        view.setUint32(ptr + 8 * i, tagOf(t), true)
        view.setFloat32(ptr + 8 * i + 4, v, true)
      })
      hb.hb_font_set_variations!(font, ptr, entries.length)
      hb.free!(ptr)
    }
    this.blobs.set(font, { blob, face, data })
    return { upem: hb.hb_face_get_upem!(face), ptr: font }
  }

  /** Release a font from {@link open}. */
  close(font: HbFont): void {
    const owned = this.blobs.get(font.ptr)
    if (!owned) return
    this.hb.hb_font_destroy!(font.ptr)
    this.hb.hb_face_destroy!(owned.face)
    this.hb.hb_blob_destroy!(owned.blob)
    this.hb.free!(owned.data)
    this.blobs.delete(font.ptr)
  }

  /** The font's vertical extents (`hhea`/`OS/2` with variations applied). */
  extents(font: HbFont): Extents {
    const { hb } = this
    const ptr = hb.malloc!(48)
    this.heap.u8.fill(0, ptr, ptr + 48)
    hb.hb_font_get_h_extents!(font.ptr, ptr)
    const v = this.heap.view
    const out = { ascender: v.getInt32(ptr, true), descender: v.getInt32(ptr + 4, true), lineGap: v.getInt32(ptr + 8, true) }
    hb.free!(ptr)
    return out
  }

  /** Shape `text` (one segment of one script and direction, typically a word) with `font`. */
  shape(font: HbFont, text: string, options: ShapeOptions = {}): Glyph[] {
    const { hb } = this
    const buffer = hb.hb_buffer_create!()
    const units = hb.malloc!(Math.max(2, text.length * 2))
    const view = this.heap.view
    for (let i = 0; i < text.length; i++) view.setUint16(units + 2 * i, text.charCodeAt(i), true)
    hb.hb_buffer_add_utf16!(buffer, units, text.length, 0, text.length)
    hb.free!(units)
    if (options.language) {
      const lang = this.ascii(options.language)
      hb.hb_buffer_set_language!(buffer, hb.hb_language_from_string!(lang, options.language.length))
      hb.free!(lang)
    }
    hb.hb_buffer_guess_segment_properties!(buffer)
    const features = options.features ?? []
    let fptr = 0
    let fcount = 0
    if (features.length) {
      fptr = hb.malloc!(16 * features.length)
      for (const f of features) {
        const s = this.ascii(f)
        if (hb.hb_feature_from_string!(s, f.length, fptr + 16 * fcount)) fcount++
        hb.free!(s)
      }
    }
    hb.hb_shape!(font.ptr, buffer, fptr, fcount)
    if (fptr) hb.free!(fptr)
    const n = hb.hb_buffer_get_length!(buffer)
    const infos = hb.hb_buffer_get_glyph_infos!(buffer, 0)
    const positions = hb.hb_buffer_get_glyph_positions!(buffer, 0)
    const v = this.heap.view
    const out: Glyph[] = []
    for (let i = 0; i < n; i++) {
      const info = infos + 20 * i
      const pos = positions + 20 * i
      out.push({
        gid: v.getUint32(info, true),
        cluster: v.getUint32(info + 8, true),
        xAdvance: v.getInt32(pos, true),
        yAdvance: v.getInt32(pos + 4, true),
        xOffset: v.getInt32(pos + 8, true),
        yOffset: v.getInt32(pos + 12, true),
      })
    }
    hb.hb_buffer_destroy!(buffer)
    return out
  }

  /**
   * A subset of `bytes` with only `glyphs` (and `.notdef`), glyph ids kept, layout tables and hints dropped, every
   * axis of a variable font pinned (to `variations`, else to its default): a static TrueType font for a PDF.
   */
  subset(bytes: Uint8Array, glyphs: Iterable<number>, variations: Variations = {}): Uint8Array {
    const { sub } = this
    const data = sub.malloc!(bytes.length)
    this.subHeap.u8.set(bytes, data)
    const blob = sub.hb_blob_create!(data, bytes.length, 1, 0, 0)
    const face = sub.hb_face_create!(blob, 0)
    const input = sub.hb_subset_input_create_or_fail!()
    if (!input) throw new Error('harfbuzz: cannot make a subset input')
    // RETAIN_GIDS 0x2 | NO_HINTING 0x1 | NOTDEF_OUTLINE 0x40
    sub.hb_subset_input_set_flags!(input, 0x2 | 0x1 | 0x40)
    const set = sub.hb_subset_input_glyph_set!(input)
    sub.hb_set_add!(set, 0)
    for (const g of glyphs) sub.hb_set_add!(set, g)
    const drop = sub.hb_subset_input_set!(input, 3 /* DROP_TABLE_TAG */)
    for (const t of ['GSUB', 'GPOS', 'GDEF', 'BASE', 'JSTF', 'MATH', 'DSIG', 'kern', 'morx', 'STAT']) sub.hb_set_add!(drop, tagOf(t))
    sub.hb_subset_input_pin_all_axes_to_default!(input, face)
    for (const [t, value] of Object.entries(variations).sort(([a], [b]) => (a < b ? -1 : 1))) {
      sub.hb_subset_input_pin_axis_location!(input, face, tagOf(t), value)
    }
    const result = sub.hb_subset_or_fail!(face, input)
    sub.hb_subset_input_destroy!(input)
    if (!result) {
      sub.hb_face_destroy!(face)
      sub.hb_blob_destroy!(blob)
      sub.free!(data)
      throw new Error('harfbuzz: the font could not be subset')
    }
    const outBlob = sub.hb_face_reference_blob!(result)
    const length = sub.hb_blob_get_length!(outBlob)
    const at = sub.hb_blob_get_data!(outBlob, 0)
    const copy = this.subHeap.u8.slice(at, at + length)
    sub.hb_blob_destroy!(outBlob)
    sub.hb_face_destroy!(result)
    sub.hb_face_destroy!(face)
    sub.hb_blob_destroy!(blob)
    sub.free!(data)
    if (length === 0) throw new Error('harfbuzz: the subset is empty')
    return copy
  }

  private ascii(s: string): number {
    const ptr = this.hb.malloc!(s.length + 1)
    const u8 = this.heap.u8
    for (let i = 0; i < s.length; i++) u8[ptr + i] = s.charCodeAt(i) & 127
    u8[ptr + s.length] = 0
    return ptr
  }
}
