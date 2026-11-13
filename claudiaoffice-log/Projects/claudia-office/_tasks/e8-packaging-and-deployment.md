---
pm-task: true
projectId: "[[claudia-office|claudia-office]]"
parentId:
id: "yz6wagfzmw2jbyb5"
title: "E8 packaging and deployment"
type: "task"
status: "in-progress"
priority: "medium"
start: "2026-11-04"
due: ""
progress: 25
assignees: []
tags: []
subtaskIds: ["[[e8.1-desktop-installers|E8.1 Desktop installers]]", "[[e8.2-install-profiles|E8.2 Install profiles]]", "[[e8.3-server-images|E8.3 Server images]]", "[[e8.4-ci-on-three-oses|E8.4 CI on three OSes]]"]
dependencies: []
createdAt: "2026-11-04T19:54:07.601Z"
updatedAt: "2026-11-10T12:00:00.000Z"
---

We need a number of packaging and installation options for claudia.

- installers for the desktop clients packaged with a server for Windows (.exe installer), Linux (.deb package), macOS - so that single users can simply install and run the entire suite on their desktop without internet connection

- installers for the desktop clients separately

- docker image for the server to host on a server or in the cloud

This epic also should remind us to really clean up the README and make it appealing, e.g. through screenshots, a link to the demo at demo.claudia-office.de, and the promotion page at www.claudia-office.de

Project: [[claudia-office|claudia-office]]

## Subtasks
- [ ] [[e8.1-desktop-installers|E8.1 Desktop installers]]
- [ ] [[e8.2-install-profiles|E8.2 Install profiles]]
- [ ] [[e8.3-server-images|E8.3 Server images]]
- [ ] [[e8.4-ci-on-three-oses|E8.4 CI on three OSes]]
