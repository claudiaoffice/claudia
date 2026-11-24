/* claudia-start.exe: what the shortcuts of Claudia Office start (UX-77, D750).
 *
 *   claudia-start.exe composes [options of the app]
 *
 * It starts the launcher of that app (node\node.exe client\bin\<app>.mjs, as the installer lays them out) without a
 * console window, writes everything the launcher and the window print to a log file, waits until it is done, and passes
 * on its exit code. If the launcher stops with an error, a message box says so, with the end of the log.
 *
 * It is a program of the GUI subsystem (no console of its own) and says nothing to a console: errors go to the log or to
 * a message box. Built by the workflow with `gcc -O2 -municode -mwindows` (packaging/windows/README.md).
 *
 * The log: %LOCALAPPDATA%\Claudia\<app>\state\launcher.log, the one of the run before as launcher.log.old.
 */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <shlobj.h>
#include <stdio.h>
#include <wchar.h>

#define PATH_MAX_CHARS 1024
#define TAIL_BYTES 1200

static const wchar_t *const APPS[] = {L"composes", L"computes", L"creates"};

static void say(const wchar_t *text, UINT icon) {
  MessageBoxW(NULL, text, L"Claudia Office", MB_OK | icon);
}

static int is_app(const wchar_t *name) {
  for (size_t i = 0; i < sizeof APPS / sizeof APPS[0]; i++)
    if (wcscmp(name, APPS[i]) == 0) return 1;
  return 0;
}

/* The folder this program is in (<root>\client). */
static int own_folder(wchar_t *out, size_t size) {
  DWORD n = GetModuleFileNameW(NULL, out, (DWORD)size);
  if (n == 0 || n >= size) return 0;
  wchar_t *slash = wcsrchr(out, L'\\');
  if (slash == NULL) return 0;
  *slash = L'\0';
  return 1;
}

/* Whether a swprintf of `size` characters wrote all of its text. */
static int whole(int written, size_t size) {
  return written >= 0 && (size_t)written < size;
}

/* One argument for a command line, as CommandLineToArgvW (and so node) reads it back: in quotes when it needs them;
 * a quote inside it is escaped, and so are the backslashes in front of that quote or of the closing one (`C:\My Dir\`). */
static int append_argument(wchar_t *line, size_t size, const wchar_t *argument) {
  size_t used = wcslen(line);
  int quote = argument[0] == L'\0' || wcspbrk(argument, L" \t\"") != NULL;
  if (used + wcslen(argument) * 2 + 4 >= size) return 0;
  wchar_t *at = line + used;
  if (used > 0) *at++ = L' ';
  if (quote) *at++ = L'"';
  size_t backslashes = 0;
  for (const wchar_t *c = argument; *c; c++) {
    if (*c == L'\\') {
      backslashes++;
      continue;
    }
    if (*c == L'"') backslashes = backslashes * 2 + 1;
    for (; backslashes > 0; backslashes--) *at++ = L'\\';
    *at++ = *c;
  }
  if (quote) backslashes *= 2;
  for (; backslashes > 0; backslashes--) *at++ = L'\\';
  if (quote) *at++ = L'"';
  *at = L'\0';
  return 1;
}

/* The state folder of the app, made if it is not there: %LOCALAPPDATA%\Claudia\<app>\state. */
static int state_folder(const wchar_t *app, wchar_t *out, size_t size) {
  wchar_t base[PATH_MAX_CHARS];
  DWORD n = GetEnvironmentVariableW(L"LOCALAPPDATA", base, PATH_MAX_CHARS);
  if (n == 0 || n >= PATH_MAX_CHARS) return 0;
  if (swprintf(out, size, L"%ls\\Claudia\\%ls\\state", base, app) < 0) return 0;
  int made = SHCreateDirectoryExW(NULL, out, NULL);
  return made == ERROR_SUCCESS || made == ERROR_ALREADY_EXISTS || made == ERROR_FILE_EXISTS;
}

/* A handle the child inherits. Every open shares everything, so that a process that inherited the log earlier (the
 * server outlives the window) never keeps the next start from replacing it. */
static HANDLE open_inheritable(const wchar_t *path, DWORD access, DWORD creation) {
  SECURITY_ATTRIBUTES inherit = {sizeof inherit, NULL, TRUE};
  return CreateFileW(path, access, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, &inherit, creation,
                     FILE_ATTRIBUTE_NORMAL, NULL);
}

/* The end of the log as text for a message box (the log is UTF-8); empty when it cannot be read. */
static void tail_of(const wchar_t *path, wchar_t *out, size_t size) {
  out[0] = L'\0';
  HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL,
                            OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
  if (file == INVALID_HANDLE_VALUE) return;
  LARGE_INTEGER length;
  char bytes[TAIL_BYTES];
  DWORD got = 0;
  if (GetFileSizeEx(file, &length)) {
    LARGE_INTEGER from;
    from.QuadPart = length.QuadPart > TAIL_BYTES ? length.QuadPart - TAIL_BYTES : 0;
    if (SetFilePointerEx(file, from, NULL, FILE_BEGIN) && ReadFile(file, bytes, TAIL_BYTES, &got, NULL) && got > 0) {
      int n = MultiByteToWideChar(CP_UTF8, 0, bytes, (int)got, out, (int)size - 1);
      out[n > 0 ? n : 0] = L'\0';
    }
  }
  CloseHandle(file);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command, int show) {
  (void)instance; (void)previous; (void)command; (void)show;

  int argc = 0;
  wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
  if (argv == NULL || argc < 2 || !is_app(argv[1])) {
    say(L"Usage: claudia-start.exe composes|computes|creates", MB_ICONERROR);
    return 2;
  }
  const wchar_t *app = argv[1];

  wchar_t client[PATH_MAX_CHARS], root[PATH_MAX_CHARS];
  if (!own_folder(client, PATH_MAX_CHARS)) {
    say(L"Claudia Office cannot tell where it is installed.", MB_ICONERROR);
    return 2;
  }
  wcscpy(root, client);
  wchar_t *slash = wcsrchr(root, L'\\');
  if (slash != NULL) *slash = L'\0';

  wchar_t node[PATH_MAX_CHARS], script[PATH_MAX_CHARS];
  int named = whole(swprintf(node, PATH_MAX_CHARS, L"%ls\\node\\node.exe", root), PATH_MAX_CHARS) &&
              whole(swprintf(script, PATH_MAX_CHARS, L"%ls\\bin\\%ls.mjs", client, app), PATH_MAX_CHARS);
  if (!named) {
    say(L"The folder Claudia Office is installed in has too long a name.", MB_ICONERROR);
    return 2;
  }
  if (GetFileAttributesW(node) == INVALID_FILE_ATTRIBUTES || GetFileAttributesW(script) == INVALID_FILE_ATTRIBUTES) {
    wchar_t text[2 * PATH_MAX_CHARS];
    swprintf(text, 2 * PATH_MAX_CHARS, L"Claudia %ls is not installed completely: %ls is missing.", app,
             GetFileAttributesW(node) == INVALID_FILE_ATTRIBUTES ? node : script);
    say(text, MB_ICONERROR);
    return 2;
  }

  wchar_t line[8 * PATH_MAX_CHARS];
  line[0] = L'\0';
  int fits = append_argument(line, 8 * PATH_MAX_CHARS, node) && append_argument(line, 8 * PATH_MAX_CHARS, script);
  for (int i = 2; fits && i < argc; i++) fits = append_argument(line, 8 * PATH_MAX_CHARS, argv[i]);
  if (!fits) {
    say(L"The options given to Claudia Office are too long.", MB_ICONERROR);
    return 2;
  }

  /* the log: the one of the run before is kept once; without a log, the output is thrown away rather than shown */
  wchar_t folder[PATH_MAX_CHARS], log[PATH_MAX_CHARS], old[PATH_MAX_CHARS];
  HANDLE out = INVALID_HANDLE_VALUE;
  log[0] = L'\0';
  if (state_folder(app, folder, PATH_MAX_CHARS)) {
    if (whole(swprintf(log, PATH_MAX_CHARS, L"%ls\\launcher.log", folder), PATH_MAX_CHARS) &&
        whole(swprintf(old, PATH_MAX_CHARS, L"%ls\\launcher.log.old", folder), PATH_MAX_CHARS)) {
      /* fails while a process of the run before (the server outlives the window) still holds the old copy: then the log
       * is written over and the run before is lost, which is better than no log */
      MoveFileExW(log, old, MOVEFILE_REPLACE_EXISTING);
      out = open_inheritable(log, GENERIC_WRITE, CREATE_ALWAYS);
    } else {
      log[0] = L'\0';
    }
  }
  if (out == INVALID_HANDLE_VALUE) out = open_inheritable(L"NUL", GENERIC_WRITE, OPEN_EXISTING);
  HANDLE in = open_inheritable(L"NUL", GENERIC_READ, OPEN_EXISTING);

  STARTUPINFOW startup;
  PROCESS_INFORMATION process;
  ZeroMemory(&startup, sizeof startup);
  startup.cb = sizeof startup;
  startup.dwFlags = STARTF_USESTDHANDLES;
  startup.hStdInput = in;
  startup.hStdOutput = out;
  startup.hStdError = out;
  if (!CreateProcessW(node, line, NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL, root, &startup, &process)) {
    wchar_t text[2 * PATH_MAX_CHARS];
    swprintf(text, 2 * PATH_MAX_CHARS, L"Claudia %ls could not be started (Windows error %lu): %ls", app,
             (unsigned long)GetLastError(), node);
    say(text, MB_ICONERROR);
    return 1;
  }
  CloseHandle(process.hThread);
  WaitForSingleObject(process.hProcess, INFINITE);
  DWORD code = 0;
  GetExitCodeProcess(process.hProcess, &code);
  CloseHandle(process.hProcess);
  CloseHandle(out);
  CloseHandle(in);

  if (code != 0) {
    wchar_t tail[TAIL_BYTES + 1], text[2 * PATH_MAX_CHARS + TAIL_BYTES + 200];
    tail_of(log, tail, TAIL_BYTES + 1);
    swprintf(text, sizeof text / sizeof text[0], L"Claudia %ls stopped with an error (code %lu).\n\nIts log: %ls\n\n%ls",
             app, (unsigned long)code, log[0] ? log : L"(none could be written)", tail);
    say(text, MB_ICONERROR);
  }
  return (int)code;
}
