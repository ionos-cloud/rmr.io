<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Architecture

```{toctree}
:maxdepth: 1
motivation
overview
client-sessions
terminology
main-components
control-path
data-path
pool-session-states
command-interface
sync-thread
```

**Overview**

RMR is a transport protocol for replicated RDMA requests. A client submits requests to be stored across a group of hosts; a server is a group member that processes them. RMR delivers each request reliably to its target group, and — when network disruptions cause replicas to diverge — resynchronizes the lost data and exposes that recovery mechanism to the user.


