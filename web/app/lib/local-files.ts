// Choosing a file of this computer (D501). In a browser tab that is the file input's own dialog. In a desktop window the
// shell shows its Open dialog instead and hands the file over: a web view there may show no dialog for a file input at
// all (WKWebView in Neutralino has none), and none opens from a menu item, which is no click in the page.
import { acceptedExtensions, currentShell } from './shell-bridge'

/** Let the person choose a file of the kinds `input` accepts. `take` gets it, and its full path when the shell says it
 * (SEC-27); `problem` gets a message for the person when the shell could not read it. A cancelled dialog calls neither.
 * In a browser tab this clicks `input`, whose own `change` handler takes the file as before: a browser never tells its
 * path. */
export async function chooseLocalFile(
  input: HTMLInputElement | null,
  take: (file: File, path: string | null) => void,
  problem: (message: string) => void = () => {},
): Promise<void> {
  const shell = currentShell()
  if (!shell?.handlesFiles) {
    input?.click()
    return
  }
  try {
    const picked = await shell.pickFile(acceptedExtensions(input?.accept ?? ''))
    if (picked) take(picked.file, picked.path)
  } catch (e) {
    problem((e as Error).message)
  }
}
