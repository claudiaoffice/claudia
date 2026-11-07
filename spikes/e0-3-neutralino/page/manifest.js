// Stand-in for the shared menu and action manifest (E5.1). One source: the shells build their
// native menus from it (Neutralino main menu); the browser draws it.
window.CLAUDIA_MANIFEST = {
  app: {
    id: "org.claudia.ShellSpike",
    name: "Claudia shell spike",
    version: "0.1",
    comments: "Test page for the E0.3 shell comparison",
    license: "placeholder"
  },
  // role: standard editing command the shell wires to the focused web view (macOS needs these for Cmd+C/V/X/A/Z).
  // accel: key for the primary modifier (Cmd on macOS, Ctrl elsewhere).
  menus: [
    { id: "file", label: "File", items: [
      { id: "file.open", label: "Open…", accel: "o" },
      { id: "file.save", label: "Save", accel: "s" },
      { id: "file.saveas", label: "Save As…" },
      { id: "file.quit", label: "Exit", accel: "q" }
    ]},
    { id: "edit", label: "Edit", items: [
      { id: "edit.undo", label: "Undo", role: "undo", accel: "z" },
      { id: "edit.redo", label: "Redo", role: "redo" },
      { id: "edit.cut", label: "Cut", role: "cut", accel: "x" },
      { id: "edit.copy", label: "Copy", role: "copy", accel: "c" },
      { id: "edit.paste", label: "Paste", role: "paste", accel: "v" },
      { id: "edit.selectall", label: "Select All", role: "selectall", accel: "a" },
      { id: "edit.pasteas", label: "Paste As…" }
    ]},
    { id: "tools", label: "Tools", items: [
      { id: "tools.ping", label: "Ping the page" }
    ]},
    { id: "help", label: "Help", items: [
      { id: "help.help", label: "Help" },
      { id: "help.about", label: "About" }
    ]}
  ]
};
