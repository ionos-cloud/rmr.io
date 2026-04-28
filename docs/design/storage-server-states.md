<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Storage Server States

```{contents}
:local:
:depth: 2
```


## Introduction

Currently, the state that determines whether IOs from the compute client can be sent to a storage node is maintained on the compute client side in the form of `rmr_clt_pool_sess` states. This state changes according to the failure type (network, IO, or storage node crash) and ensures that a failed session does not return to normal state (where IOs can be sent) without a proper map update. But this information is lost in case of a compute client crash, which makes it a single point of failure.

To ensure this information is not lost in case of a single failure (compute client crash), it must also be maintained on the storage nodes. This allows the system to enforce sanity checks and permit only valid state transitions. Additionally, the pool on the storage server side has other processes — such as backend store registration and map creation — that require additional state management.

```{image} ../_static/images/design/IO_perm_states-storage_states.drawio.png
:width: 100%
```

## States

The allowed states for this param and their descriptions are as follows.

### RMR\_SRV\_POOL\_STATE\_EMPTY

State once the pool is created, before any backend store is registered.

Pool has no store registered and no sessions.

In this state no sessions can join. To understand why: for a storage node to be a member of a pool, it must be added as a member and a map for that member must be created. Both of these happen simultaneously.

- For a pool being created: when nodes (replication legs) are added in "create" mode, member addition and map creation happen at this stage. This information must then be persisted in the backend store along with the metadata.
- For an assemble (store add): the pool must read the metadata from the backend to know how many members are part of that pool and who they are, after which map creation happens. Without the member info, map, and backend store, the storage node cannot process or serve anything.

Both steps require a backend store to be registered. Allowing a session join or rejoin without a store is therefore meaningless.

In this state,

- No pool\_sess join/rejoin is allowed.
- No IO is allowed.

This state is reached from REGISTERED when the backend store is unregistered and no sessions are present, or from NO\_IO when the last session leaves and the store has already been unregistered.

### RMR\_SRV\_POOL\_STATE\_REGISTERED

State once the backend store is registered and before any session has joined.

When the store is registered, the `marked_create` flag on the server pool is set to `true` if
the registration was called with "create" mode, and `false` otherwise. This flag is then used
to gate which join modes are accepted: only the join mode that matches the registration mode
is allowed. The flag is cleared once a successful create-mode join completes.

For a store register with "create" mode (`marked_create = true`),
- Only self member info and map creation happens.
- Non-sync join with "create" mode is allowed; all other join modes (assemble, sync) are rejected.

For a store register with "add" (assemble) mode (`marked_create = false`),
- The member addition and map creation for all the members would happen while transitioning to this stage.
- Since all information about storage nodes and map is available, all join/rejoins are allowed.
- Non-sync join with "create" mode is not allowed.

Transitions out of REGISTERED:

- Non-sync join with "create" mode → CREATED
- Non-sync join with "assemble" or rejoin mode → NO\_IO (a map update is required before IOs can resume)

In this state,

- No IO is allowed.

This state is also reached from NO\_IO when the last session leaves and the store is still registered.

### RMR\_SRV\_POOL\_STATE\_CREATED

This state is reached only once, when the pool is being created for the first time.

Transition to this state happens only from REGISTERED, when a non-sync join with "create" mode is received. Sync session joins and all assemble/rejoin modes are not allowed.

Pool has sessions, but is not enabled.

In this state,

- No IO is allowed.

### RMR\_SRV\_POOL\_STATE\_NORMAL

State in which IOs are allowed.

Pool has an updated map and can serve IOs.

This state is reached from,

- An enable for a pool in CREATED state.
- A last\_io and/or map update completing for a pool in NO\_IO state.
- A direct enable for a pool in NO\_IO state when the compute client determines that the last NORMAL session went directly to failure (was\_last\_authoritative recovery): the dirty map on that node is already complete, so no map update is needed before re-enabling it.

### RMR\_SRV\_POOL\_STATE\_NO\_IO

This state can be reached in either of the following two ways:

- While assembling an existing pool. In REGISTERED state, a non-sync join/rejoin arrives and the pool is NOT marked "create". The pool waits for a compute client-triggered last\_io and/or map update before transitioning to NORMAL.
- Any kind of failure (discussed in detail below).

A pool in NORMAL state can transition to NO\_IO state after encountering one of the following errors/failures.

- IO/network error.
- Manual maintenance mode set.

In this state,

- No IOs are allowed.

Once the error is corrected, the pool stays in the same state and waits for recovery. Recovery can happen in one of the following ways:

- A last\_io and/or map update from the compute client.
- A direct enable from the compute client when was\_last\_authoritative recovery applies (no map update needed).

The error correction can happen in the following scenarios.

- RTRS network event for reconnection
- A store check was successful.
- A rejoin message was received.

See also: [Client Session States](client-session-states.md).
