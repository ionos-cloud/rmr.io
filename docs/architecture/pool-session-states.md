<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Pool and Session States


## RMR pool states

RMR pool object itself has a very simple lifetime. They can be created and destroyed. There are few more conditional points around it.
1) An RMR client pool cannot be deleted if it has sessions. The sessions have to be deleted for the pool to be deleted.
2) An RMR server pool cannot be deleted if it has a backend store registered.
### Client pool states
The client pool tracks its lifecycle with the following states (defined in `rmr_clt_pool_state`):
- **JOINED**: At least one session has been added to the pool.
- **IN_USE**: The pool is in use by an upper layer client (e.g. BRMR).
Note: The header `rmr.h` also defines a `rmr_pool_state` enum with CREATED, JOINED, ONLINE, DEGRADED, and SYNCING values. These are not currently used in the codebase and are reserved for future use.
### Server pool states
This section documents the low-level server pool runtime states exposed via sysfs (defined in `rmr_srv_pool_state`). For the broader cluster-management lifecycle see [Cluster Management](../guide/cluster-management.md).
- **EMPTY**: Pool has no store registered.
- **CREATED**: Pool created but not yet enabled.
- **NORMAL**: Pool operating normally, IO allowed.
- **NO_IO**: Pool exists but IO is blocked (e.g., during map updates or synchronization).
## RMR client session states
Client pool session states are critical to the correct working of RMR (defined in `rmr_clt_pool_sess_state`):
- **CREATED**: Session has been created but not yet enabled.
- **NORMAL**: Session is active and can send/receive IO.
- **FAILED**: Session has failed due to RTRS link disconnect or IO error. The user can also disable the session manually.
- **RECONNECTING**: RTRS link has been restored, or a successful store check has occurred. A map update is required before IO can resume.
- **REMOVING**: Session is being removed from the pool.
## Storage server IO states
The server pool state (see above) controls whether a storage node can serve IOs. Transitions between NORMAL and NO_IO are managed automatically during map updates, maintenance mode, and failure recovery.
