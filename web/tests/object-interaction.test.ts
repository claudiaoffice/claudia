import { describe, expect, it, vi } from 'vitest'
import { useObjectInteraction, type ObjectHost } from '~/lib/object-interaction'
import type { Commit, Subject } from '~/lib/object-gestures'

function setup(extra: Partial<Subject> = {}, host: Partial<ObjectHost> = {}) {
  const subject: Subject = { id: 'o1', frame: { x: 100, y: 100, w: 300, h: 200 }, rotation: 0, aspect: null, grid: null, ...extra }
  const commits: Commit[] = []
  const commit = vi.fn(async (c: Commit) => void commits.push(c))
  const base: ObjectHost = {
    bounds: { w: 1600, h: 900 },
    scale: 1,
    readonly: false,
    toUnits: (e) => ({ x: e.clientX, y: e.clientY }),
    subject: (id) => (id === 'o1' ? subject : null),
    commit,
  }
  const interaction = useObjectInteraction({ ...base, ...host })
  return { interaction, commits, commit }
}

describe('a press on an object', () => {
  it('moves it while the pointer is down (a preview), and sends one move on release', async () => {
    const { interaction, commits } = setup()
    interaction.begin('o1', 'move', { clientX: 150, clientY: 150 })
    expect(interaction.frameOf('o1')).toBeNull() // nothing yet: still a click
    interaction.move({ clientX: 250, clientY: 170 })
    expect(interaction.frameOf('o1')).toEqual({ x: 200, y: 120, w: 300, h: 200 })
    expect(await interaction.release()).toEqual({ kind: 'move', id: 'o1', x: 200, y: 120 })
    expect(commits).toHaveLength(1)
    expect(interaction.frameOf('o1')).toBeNull() // the answer is in, the preview goes
  })

  it('sends nothing for a click', async () => {
    const { interaction, commit } = setup()
    interaction.begin('o1', 'move', { clientX: 150, clientY: 150 })
    expect(await interaction.release()).toBeNull()
    expect(commit).not.toHaveBeenCalled()
  })

  it('shows the preview only on the object that is held', () => {
    const { interaction } = setup()
    interaction.begin('o1', 'move', { clientX: 150, clientY: 150 })
    interaction.move({ clientX: 300, clientY: 300 })
    expect(interaction.frameOf('o2')).toBeNull()
  })

  it('does not begin for an object that is gone', () => {
    expect(setup().interaction.begin('gone', 'move', { clientX: 0, clientY: 0 })).toBe(false)
  })
})

describe('Esc', () => {
  it('drops a drag in progress: the object is as it was and nothing is sent', async () => {
    const { interaction, commit } = setup()
    interaction.begin('o1', 'move', { clientX: 150, clientY: 150 })
    interaction.move({ clientX: 400, clientY: 400 })
    expect(interaction.cancel()).toBe(true)
    expect(interaction.frameOf('o1')).toBeNull()
    expect(await interaction.release()).toBeNull()
    expect(commit).not.toHaveBeenCalled()
  })
  it('says there was nothing to drop, so the caller may take it to mean "leave the selection"', () => {
    expect(setup().interaction.cancel()).toBe(false)
  })
})

describe('the turn handle', () => {
  it('shows the angle while held and sends one rotation on release', async () => {
    const { interaction, commits } = setup()
    interaction.begin('o1', 'turn', { clientX: 250, clientY: 0 })
    interaction.move({ clientX: 600, clientY: 200 }) // the middle is (250, 200): straight to the right
    expect(interaction.turningNow('o1')).toBe(true)
    expect(interaction.rotationOf('o1')).toBe(90)
    await interaction.release()
    expect(commits).toEqual([{ kind: 'rotate', id: 'o1', rotation: 90 }])
  })
})

describe('Rotate By…', () => {
  it('previews angles on the object and sends one turn on Done', async () => {
    const { interaction, commits } = setup()
    expect(interaction.startRotateBy('o1')).toBe(true)
    interaction.previewRotateBy(45)
    expect(interaction.rotationOf('o1')).toBe(45)
    expect(await interaction.finishRotateBy(45)).toEqual({ kind: 'rotate', id: 'o1', rotation: 45 })
    expect(commits).toHaveLength(1)
    expect(interaction.rotationOf('o1')).toBeNull()
  })
  it('sends nothing when Done is pressed at the angle the object had, and Esc drops the preview', async () => {
    const { interaction, commit } = setup({ rotation: 30 })
    interaction.startRotateBy('o1')
    interaction.previewRotateBy(60)
    expect(interaction.cancel()).toBe(true)
    expect(interaction.rotationOf('o1')).toBeNull()
    interaction.startRotateBy('o1')
    expect(await interaction.finishRotateBy(30)).toBeNull()
    expect(commit).not.toHaveBeenCalled()
  })
})

describe('a viewer', () => {
  it('may press but nothing is ever sent, and Rotate By… does not open', async () => {
    const { interaction, commit } = setup({}, { readonly: true })
    interaction.begin('o1', 'move', { clientX: 150, clientY: 150 })
    interaction.move({ clientX: 400, clientY: 400 })
    expect(interaction.frameOf('o1')).toBeNull()
    expect(await interaction.release()).toBeNull()
    expect(commit).not.toHaveBeenCalled()
    expect(interaction.startRotateBy('o1')).toBe(false)
  })
})

describe('the answer to a commit', () => {
  it('is waited for: the preview stays on screen until the server has answered', async () => {
    let answer!: () => void
    const { interaction } = setup({}, { commit: () => new Promise<void>((resolve) => (answer = resolve)) })
    interaction.begin('o1', 'move', { clientX: 150, clientY: 150 })
    interaction.move({ clientX: 250, clientY: 150 })
    const done = interaction.release()
    expect(interaction.frameOf('o1')).not.toBeNull()
    answer()
    await done
    expect(interaction.frameOf('o1')).toBeNull()
  })
})
