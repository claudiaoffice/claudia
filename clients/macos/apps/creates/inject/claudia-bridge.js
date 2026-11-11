"use strict";
(() => {
  // src/menu.ts
  function isSubmenu(entry) {
    return "items" in entry;
  }
  var ROLE_SHORTCUT = {
    "undo:": "z",
    "cut:": "x",
    "copy:": "c",
    "paste:": "v"
    // 'redo:' deliberately absent -- see this module's top comment.
  };
  function gtkAccelToMacShortcut(accelerator) {
    const match = /^<Primary>([A-Za-z])$/.exec(accelerator);
    return match ? match[1].toLowerCase() : null;
  }
  function buildItem(action) {
    const item = { id: action.id, text: action.label };
    if (action.checkable) item.isChecked = false;
    if (action.role) {
      item.action = action.role;
      const roleShortcut = ROLE_SHORTCUT[action.role];
      if (roleShortcut) item.shortcut = roleShortcut;
    } else {
      const translated = action.accelerators.map(gtkAccelToMacShortcut).find((s) => s !== null);
      if (translated) item.shortcut = translated;
    }
    return item;
  }
  function buildEntry(entry) {
    if (isSubmenu(entry)) {
      return { text: entry.label, menuItems: entry.items.map(buildItem) };
    }
    return buildItem(entry);
  }
  var SEPARATOR = { text: "-" };
  function buildMenu(menu, omit) {
    const sections = menu.sections.map((section) => section.filter((entry) => isSubmenu(entry) || !omit.has(entry.id))).filter((section) => section.length > 0);
    const items = [];
    sections.forEach((section, index) => {
      if (index > 0) items.push(SEPARATOR);
      items.push(...section.map(buildEntry));
    });
    return { text: menu.label, menuItems: items };
  }
  function buildMainMenu(listing, appTitle) {
    const about = findAction(listing, "help.about");
    const quit = findAction(listing, "file.quit");
    const relocated = new Set([about?.id, quit?.id].filter((id) => id !== void 0));
    const appMenu = {
      text: appTitle,
      menuItems: [about, quit].filter((a) => a !== void 0).map(buildItem)
    };
    return [appMenu, ...listing.menus.map((menu) => buildMenu(menu, relocated))];
  }
  function findAction(listing, id) {
    for (const menu of listing.menus) {
      for (const section of menu.sections) {
        for (const entry of section) {
          if (!isSubmenu(entry) && entry.id === id) return entry;
        }
      }
    }
    return void 0;
  }

  // src/page-bridge.ts
  function routeMenuClick(id, known, checkedState = {}) {
    if (id === "file.quit") return { kind: "quit" };
    const action = known.find((a) => a.id === id);
    const target = action?.checkable ? nextCheckedTarget(checkedState[id]) : void 0;
    return { kind: "forward", action: id, target };
  }
  function nextCheckedTarget(current) {
    return current ? "off" : "on";
  }
  function applyActionStates(menu, states) {
    const patchOne = (item) => {
      const patched = item.menuItems ? { ...item, menuItems: item.menuItems.map(patchOne) } : { ...item };
      const state = item.id ? states[item.id] : void 0;
      if (state) {
        if (state.checked !== void 0) patched.isChecked = state.checked;
        if (state.enabled !== void 0) patched.isDisabled = !state.enabled;
        if (state.label !== void 0) patched.text = state.label;
      }
      return patched;
    };
    return menu.map(patchOne);
  }
  function collectKnownActions(menu) {
    const out = [];
    for (const item of menu) {
      if (item.menuItems) out.push(...collectKnownActions(item.menuItems));
      else if (item.id) out.push({ id: item.id, checkable: item.isChecked !== void 0 });
    }
    return out;
  }
  function installBridge(neutralino, win, listing, appTitle) {
    let menu = buildMainMenu(listing, appTitle);
    const known = collectKnownActions(menu);
    const checkedState = {};
    for (const item of known) if (item.checkable) checkedState[item.id] = false;
    void neutralino.window.setMainMenu(menu);
    win.webkit = win.webkit ?? {};
    win.webkit.messageHandlers = win.webkit.messageHandlers ?? {};
    win.webkit.messageHandlers.claudia = {
      postMessage(raw) {
        let message;
        try {
          message = JSON.parse(raw);
        } catch {
          return;
        }
        if (!message || typeof message !== "object") return;
        const { type } = message;
        if (type === "hello") {
          win.__claudiaShell?.receive(
            JSON.stringify({ type: "welcome", contract: 1, shell: "claudia-macos", capabilities: ["native-menu", "actions"] })
          );
        } else if (type === "action_state") {
          const { states } = message;
          if (states) {
            menu = applyActionStates(menu, states);
            void neutralino.window.setMainMenu(menu);
          }
        }
      }
    };
    void neutralino.events.on("mainMenuItemClicked", (event) => {
      const { id } = event.detail ?? {};
      if (!id) return;
      const route = routeMenuClick(id, known, checkedState);
      if (route.kind === "quit") {
        void neutralino.app.exit();
        return;
      }
      if (route.target !== void 0) checkedState[id] = route.target === "on";
      win.__claudiaShell?.receive(JSON.stringify({ type: "action", action: route.action, target: route.target }));
    });
  }

  // src/file-dialog.ts
  function parseAcceptExtensions(accept) {
    const extensions = [];
    for (const token of accept.split(",")) {
      const trimmed = token.trim();
      if (!trimmed.startsWith(".")) continue;
      const ext = trimmed.slice(1).toLowerCase();
      if (ext && !extensions.includes(ext)) extensions.push(ext);
    }
    return extensions;
  }
  var MIME_BY_EXTENSION = {
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    gif: "image/gif",
    bmp: "image/bmp",
    svg: "image/svg+xml",
    png: "image/png"
  };
  function guessMimeType(path) {
    const dot = path.lastIndexOf(".");
    if (dot === -1) return "application/octet-stream";
    return MIME_BY_EXTENSION[path.slice(dot + 1).toLowerCase()] ?? "application/octet-stream";
  }
  function basename(path) {
    const slash = path.lastIndexOf("/");
    return slash === -1 ? path : path.slice(slash + 1);
  }
  async function pickFiles(neutralino, input) {
    const extensions = parseAcceptExtensions(input.accept);
    const filters = extensions.length > 0 ? [{ name: "Allowed files", extensions }] : void 0;
    const paths = await neutralino.os.showOpenDialog(void 0, { filters, multiSelections: input.multiple });
    if (paths.length === 0) return;
    const files = [];
    for (const path of paths) {
      const buffer = await neutralino.filesystem.readBinaryFile(path);
      files.push(new File([buffer], basename(path), { type: guessMimeType(path) }));
    }
    const transfer = new DataTransfer();
    for (const file of files) transfer.items.add(file);
    input.files = transfer.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }
  function installFileDialogBridge(neutralino, doc) {
    doc.addEventListener(
      "click",
      (event) => {
        const target = event.target;
        if (!(target instanceof HTMLInputElement) || target.type !== "file") return;
        event.preventDefault();
        pickFiles(neutralino, target).catch((error) => {
          console.error("[claudia-bridge] could not open the native file picker:", error);
        });
      },
      { capture: true }
    );
  }

  // src/inject-entry.ts
  function boot() {
    const neutralino = window.Neutralino;
    if (!neutralino) {
      console.warn("[claudia-bridge] window.Neutralino is not present; running without a native shell");
      return;
    }
    const listing = JSON.parse('{\n  "app": "creates",\n  "header_toggles": [],\n  "menus": [\n    {\n      "label": "File",\n      "sections": [\n        [\n          {\n            "accelerators": [\n              "<Primary>n"\n            ],\n            "checkable": false,\n            "id": "file.new",\n            "kind": "page",\n            "label": "New",\n            "role": null\n          },\n          {\n            "accelerators": [\n              "<Primary>o"\n            ],\n            "checkable": false,\n            "id": "file.open",\n            "kind": "page",\n            "label": "Open\\u2026",\n            "role": null\n          }\n        ],\n        [\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "file.save",\n            "kind": "page",\n            "label": "Save",\n            "role": null\n          },\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "file.save-as",\n            "kind": "page",\n            "label": "Save New Checkpoint\\u2026",\n            "role": null\n          },\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "file.download",\n            "kind": "page",\n            "label": "Download",\n            "role": null\n          }\n        ],\n        [\n          {\n            "items": [\n              {\n                "accelerators": [],\n                "checkable": false,\n                "id": "file.manage.share",\n                "kind": "page",\n                "label": "Share\\u2026",\n                "role": null\n              },\n              {\n                "accelerators": [],\n                "checkable": false,\n                "id": "file.manage.assign-owner",\n                "kind": "page",\n                "label": "Assign New Owner\\u2026",\n                "role": null\n              },\n              {\n                "accelerators": [],\n                "checkable": false,\n                "id": "file.manage.accept-owner",\n                "kind": "page",\n                "label": "Accept Ownership\\u2026",\n                "role": null\n              },\n              {\n                "accelerators": [],\n                "checkable": false,\n                "id": "file.manage.leave",\n                "kind": "page",\n                "label": "Leave Document\\u2026",\n                "role": null\n              },\n              {\n                "accelerators": [],\n                "checkable": false,\n                "id": "file.manage.export",\n                "kind": "page",\n                "label": "Export\\u2026",\n                "role": null\n              },\n              {\n                "accelerators": [],\n                "checkable": false,\n                "id": "file.manage.delete",\n                "kind": "page",\n                "label": "Delete From Server\\u2026",\n                "role": null\n              }\n            ],\n            "label": "Manage"\n          }\n        ],\n        [\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "file.close",\n            "kind": "page",\n            "label": "Close Document",\n            "role": null\n          },\n          {\n            "accelerators": [\n              "<Primary>q"\n            ],\n            "checkable": false,\n            "id": "file.quit",\n            "kind": "shell",\n            "label": "Quit",\n            "role": null\n          }\n        ]\n      ]\n    },\n    {\n      "label": "Edit",\n      "sections": [\n        [\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "edit.undo",\n            "kind": "page",\n            "label": "Undo",\n            "role": "undo:"\n          },\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "edit.redo",\n            "kind": "page",\n            "label": "Redo",\n            "role": "redo:"\n          }\n        ],\n        [\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "edit.copy",\n            "kind": "page",\n            "label": "Copy",\n            "role": "copy:"\n          },\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "edit.cut",\n            "kind": "page",\n            "label": "Cut",\n            "role": "cut:"\n          },\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "edit.paste",\n            "kind": "page",\n            "label": "Paste",\n            "role": "paste:"\n          },\n          {\n            "items": [\n              {\n                "accelerators": [],\n                "checkable": false,\n                "id": "edit.paste-as-plain",\n                "kind": "page",\n                "label": "Plain Text",\n                "role": null\n              }\n            ],\n            "label": "Paste As"\n          }\n        ],\n        [\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "edit.new-slide",\n            "kind": "page",\n            "label": "New Slide",\n            "role": null\n          }\n        ],\n        [\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "edit.edit-text",\n            "kind": "page",\n            "label": "Edit Text",\n            "role": null\n          },\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "edit.text-box",\n            "kind": "page",\n            "label": "Text Box",\n            "role": null\n          }\n        ],\n        [\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "edit.delete",\n            "kind": "page",\n            "label": "Delete",\n            "role": null\n          }\n        ]\n      ]\n    },\n    {\n      "label": "Format",\n      "sections": [\n        [\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "format.none",\n            "kind": "page",\n            "label": "No Styles Yet",\n            "role": null\n          }\n        ]\n      ]\n    },\n    {\n      "label": "View",\n      "sections": [\n        [\n          {\n            "accelerators": [],\n            "checkable": true,\n            "id": "view.authors",\n            "kind": "page",\n            "label": "Show Who Wrote What",\n            "role": null\n          },\n          {\n            "accelerators": [],\n            "checkable": true,\n            "id": "view.panel",\n            "kind": "page",\n            "label": "History and Chat",\n            "role": null\n          },\n          {\n            "accelerators": [],\n            "checkable": true,\n            "id": "view.dark",\n            "kind": "page",\n            "label": "Dark Mode",\n            "role": null\n          }\n        ]\n      ]\n    },\n    {\n      "label": "Tools",\n      "sections": [\n        [\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "tools.ask",\n            "kind": "page",\n            "label": "Ask the Assistant\\u2026",\n            "role": null\n          }\n        ]\n      ]\n    },\n    {\n      "label": "Config",\n      "sections": [\n        [\n          {\n            "accelerators": [\n              "F1"\n            ],\n            "checkable": false,\n            "id": "config.shortcuts",\n            "kind": "page",\n            "label": "Shortcuts",\n            "role": null\n          }\n        ]\n      ]\n    },\n    {\n      "label": "Help",\n      "sections": [\n        [\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "help.ask",\n            "kind": "page",\n            "label": "Ask ai",\n            "role": null\n          },\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "help.how-to",\n            "kind": "page",\n            "label": "How Do I\\u2026?",\n            "role": null\n          },\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "help.docs",\n            "kind": "page",\n            "label": "Documentation",\n            "role": null\n          },\n          {\n            "accelerators": [],\n            "checkable": false,\n            "id": "help.about",\n            "kind": "shell",\n            "label": "About Claudia Creates",\n            "role": null\n          }\n        ]\n      ]\n    }\n  ]\n}\n');
    installBridge(neutralino, window, listing, "Claudia Creates");
    installFileDialogBridge(neutralino, document);
  }
  boot();
})();
