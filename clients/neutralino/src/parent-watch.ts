// Ends the core with the process that started it (CODE-97, D753). Neutralino starts the core as its extension and does
// not end it when it ends itself or is ended ("Neutralino doesn't send kill signals to extension processes", its
// release notes for v4.0.0); the core ends when its link to Neutralino breaks, but on Windows that link was seen to stay
// up after Neutralino was killed; and the core's parent there is a shell that outlives Neutralino. The window's own
// process (the page knows it as NL_PID and tells the core) being gone is a reason that does not depend on the link.

export interface ParentWatch {
  /** The process to wait for: the one that started this one, or the window. */
  pid: number
  /** For the parent: the process that is this one's parent now, another one when the first is gone, on a Mac or Linux. */
  parentNow?: () => number
  /** Whether a process is there: `kill(pid, 0)`, which sends nothing. */
  alive?: (pid: number) => boolean
  /** Said once, with the reason for the log. */
  onGone: (reason: string) => void
  intervalMs?: number
}

const LOOK_EVERY_MS = 1000

function processIsThere(pid: number): boolean {
  try {
    process.kill(pid, 0)
    return true
  } catch (problem) {
    // EPERM: it is there, and not ours to signal
    return (problem as NodeJS.ErrnoException).code === 'EPERM'
  }
}

/** Looks every second; returns what stops the looking. A pid of 0 or 1 (the init process, a detached start) has nobody
 * to wait for and is never reported gone. With `parentNow`, the process is also gone when it is no longer this one's
 * parent. */
export function watchProcess(watch: ParentWatch): () => void {
  if (watch.pid <= 1) return () => {}
  const alive = watch.alive ?? processIsThere
  let said = false
  const timer = setInterval(() => {
    if (said) return
    if ((watch.parentNow !== undefined && watch.parentNow() !== watch.pid) || !alive(watch.pid)) {
      said = true
      clearInterval(timer)
      watch.onGone(`the process ${watch.pid} is gone`)
    }
  }, watch.intervalMs ?? LOOK_EVERY_MS)
  // The looking must not keep a process alive that has nothing else to do.
  timer.unref()
  return () => clearInterval(timer)
}

/** The process that started this one: the window's own process when Neutralino starts the core directly. */
export function watchParent(watch: ParentWatch): () => void {
  return watchProcess({ parentNow: () => process.ppid, ...watch })
}
