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

RMR is a transport protocol. Its user can send requests to be stored in a group, and it can receive requests sent to a group member for processing. We call the user submitting the requests the "client" and the user responsible for processing requests the "server". On the one hand, RMR provides a user with a reliable way of delivering an RDMA request to a named group of hosts; on the other hand, it is responsible for resynchronization of data lost during network disruptions in a given group, and exposes the internal mechanism for doing so to the user.

**Client interface**

**Server interface**
