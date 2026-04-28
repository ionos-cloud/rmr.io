<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Control Path

The control path covers the non-IO exchanges that keep an RMR pool coherent: admitting and removing sessions, propagating membership, reconciling dirty maps after a disruption, and admitting storage nodes back into service. Control messages share the RTRS session used for IO and are identified by the `rmr_msg_cmd_type` enum (`RMR_CMD_*`). For the IO flow itself, see [Data Path](data-path.md).

## Backend store registration

An RMR server pool cannot serve IO until a backend store is registered with it. On each storage node, the `brmr-server` module opens the block device and calls `rmr_srv_register()` to attach it as the pool's `io_store`. Registration is the server-side event that moves the server pool out of `EMPTY`, establishes the member's dirty map, and marks the pool ready to accept session joins. `rmr_srv_unregister()` reverses it.

Registration carries a `rmr_srv_register_disk_mode` that selects one of three behaviors (`RMR_SRV_DISK_CREATE`, `RMR_SRV_DISK_ADD`, `RMR_SRV_DISK_REPLACE`). Unregistration carries a `delete` flag. These map to the four user-facing sysfs entries on brmr-server: `create_store`, `add_store`, `remove_store`, `delete_store`. See [Cluster Management](../guide/cluster-management.md) for the user-facing walkthrough; the per-mode semantics are described in [Attach and detach modes](#attach-and-detach-modes) below.

Store state on the brmr side is tracked in `brmr_srv_blk_dev->state` as `BRMR_SRV_STORE_OPEN` / `BRMR_SRV_STORE_MAPPED`. Only an open *and* mapped store passes `io_allowed()`; this is the check used by the recovery thread's store probe (see [Store check](#store-check)).

## Pool session lifecycle

A client session attaches to a storage node via `RMR_CMD_JOIN_POOL`, is admitted to service via `RMR_CMD_ENABLE_POOL`, re-attaches after a link disruption via `RMR_CMD_REJOIN_POOL`, and detaches via `RMR_CMD_LEAVE_POOL`. Each attach and detach is also propagated to every other non-FAILED, non-REMOVING peer via `RMR_CMD_POOL_INFO` (`rmr_clt_send_pool_info()`) so all storage nodes keep a consistent view of membership.

- `RMR_CMD_JOIN_POOL` carries per-pool parameters (`chunk_size`, `queue_depth`), a `create` flag, and `rmr_pool_member_info` describing the peer `member_id`s the client is aware of. The server replies with the `member_id` it has assigned to this session along with pool-wide properties (protocol version, `mapped_size`).
- `RMR_CMD_REJOIN_POOL` uses the same message body as join but with `rejoin=true`; it does not assign a new `member_id` because the server-side pool state is preserved across the disruption. The session participates in recovery but is not yet allowed to serve IO.
- `RMR_CMD_ENABLE_POOL` admits the session into service and is the transition that brings an `rmr_clt_pool_sess` to `NORMAL`. Enable is also embedded in the final `RMR_CMD_MAP_DONE` of a map update, which is how reconnected sessions get promoted at the end of reconciliation (see [Map update](#map-update)).
- `RMR_CMD_LEAVE_POOL` carries a `delete` flag selecting whether the removal is permanent or transient (see below).
- `RMR_CMD_POOL_INFO` carries the affected `member_id`, an ADD/REMOVE operation, and a mode (CREATE/ASSEMBLE/DELETE/DISASSEMBLE) matching the join/leave that triggered it.

## Attach and detach modes

Attach and detach each have two variants, paired across the brmr-store layer, the session-level command, and the peer propagation layer so every layer agrees on intent.

### Create vs. Assemble

Used when a node joins a pool, chosen to match whether the pool already exists on that node's disk.

**Create** establishes the pool on the storage node for the first time.

- Store (`create_store`, `RMR_SRV_DISK_CREATE`): brmr-server writes new on-disk pool metadata on the block device and rmr-server creates a fresh dirty map for the member. Rejected if sessions or a map for this `member_id` already exist. The server pool records `marked_create=true` for validation of the first joining client session.
- Session (`RMR_CMD_JOIN_POOL` with `create=true`): accepted only if the server pool was registered with `marked_create`. The server uses `rmr_pool_member_info` in the message to populate `stg_members` and create dirty maps for the peers the client is aware of.
- Propagation (`RMR_CMD_POOL_INFO` with `ADD` + `CREATE`): each peer calls `rmr_srv_add_store_member()` to create a `stg_members` entry and dirty map for the new member. If the `dirty` flag is set, the peer marks the new member's map fully dirty so subsequent piggyback IOs build up real dirty entries the new node will need to catch up on.

**Assemble** is used when the pool's state already exists on the storage node's disk (e.g. after a compute-client crash where the storage retains data but the client view is gone).

- Store (`add_store`, `RMR_SRV_DISK_ADD`): brmr-server validates the existing on-disk pool metadata; rmr-server refreshes `pool_md` from disk (`rmr_srv_refresh_md()`) and preserves the existing dirty map.
- Session (`RMR_CMD_JOIN_POOL` with `create=false`): the server pool is unchanged by the handshake. The client separately reads `pool_md` from the server (via `RMR_CMD_MD_SEND`) to learn membership and rebuild its client-side maps to match. The session goes to `RECONNECTING` and waits for a map update before being promoted to `NORMAL`.
- Propagation (`RMR_CMD_POOL_INFO` with `ADD` + `ASSEMBLE`): peers verify that the member's `stg_members` entry and dirty map already exist; no new state is created. A missing entry is an error.

A third store-only mode, **Replace** (`RMR_SRV_DISK_REPLACE`), covers the case where the old disk is gone and a new empty disk is inserted. Server-side, the existing map is erased, a fresh map is created, and the `RMR_STORE_IS_REPLACE` bit is set on `map_ver` so that peers discover the replacement and coordinate discards of the dirty entries they still hold for this member (see [Discard coordination](#discard-coordination)). There is no corresponding session mode — the session simply assembles on top of the replaced store.

```{note}
Replace is currently disabled. The user-facing `add_store mode=replace` path in brmr-server rejects the request, and the surrounding flows that depend on it (discard coordination and the replace-triggered parts of last-IO reconciliation) are not exercised in normal operation. Most of the underlying code exists but has known edge cases and missing peer-to-peer info exchange that need further work.
```

### Delete vs. Disassemble

Used when a node is removed from a pool, chosen to match whether the removal is permanent or whether the node is expected to come back.

**Delete** is permanent removal (decommissioning).

- Store (`delete_store`, `rmr_srv_unregister(delete=true)`): brmr-server closes the block device and wipes the pool metadata from disk. The disk must be reformatted with `create_store` before it can be reused in any pool.
- Session (`RMR_CMD_LEAVE_POOL` with `delete=true`): the server deletes the dirty maps of all other members on this node (`rmr_srv_process_leave_delete()`) — this node no longer needs to track dirty data for anyone.
- Propagation (`RMR_CMD_POOL_INFO` with `REMOVE` + `DELETE`): peers call `rmr_srv_delete_store_member()`, erasing the member's `stg_members` entry and dirty map.

**Disassemble** is transient removal (maintenance, graceful shutdown with planned return).

- Store (`remove_store`, `rmr_srv_unregister(delete=false)`): brmr-server closes the block device but preserves the on-disk pool metadata so the disk can be reattached later via `add_store`.
- Session (`RMR_CMD_LEAVE_POOL` with `delete=false`): no map changes on the server side — state is preserved for a subsequent reassemble.
- Propagation (`RMR_CMD_POOL_INFO` with `REMOVE` + `DISASSEMBLE`): peers keep the member's `stg_members` entry and dirty map intact. IOs arriving while the member is away continue to accumulate dirty entries for it via the piggyback mechanism, so the state needed for resync on reassembly is built up during the detachment.

## Map update

When a session is brought back into service, its dirty map must be reconciled against the pool before it is allowed to serve IO. The client picks an authoritative session (a `NORMAL` one, or the single `was_last_authoritative` session surviving a full-pool failure) and orchestrates a three-command handshake per receiving session:

1. `RMR_CMD_MAP_READY` — sent to the receiving session to prepare it to accept a map.
2. `RMR_CMD_MAP_SEND` — sent to the authoritative session with the receiver's `member_id`, instructing it to transfer its map in chunks (via `RMR_CMD_SEND_MAP_BUF` / `RMR_CMD_MAP_BUF_DONE`).
3. `RMR_CMD_MAP_DONE` — sent to the receiving session once the transfer is complete. It carries an `enable` flag that controls whether the session transitions to `NORMAL` at the end.

The entry point is `rmr_clt_spread_map()`. The `enable` flag lets the same handshake cover two cases: admitting a freshly reconnected session to service (`enable=true`) and propagating an up-to-date map to sessions that must not yet be admitted (`enable=false`).

If IOs are already flowing through a `NORMAL` session at the time of the spread, the client freezes IO for the duration of the exchange so new writes cannot race with reconciliation.

If any step fails, the receiving session is sent `RMR_CMD_MAP_DISABLE` to discard the partial state.

## Map version

Every pool carries a monotonically advancing `map_ver` in `struct rmr_pool_md`. It advances whenever the authoritative view changes and is used during recovery to pick the most up-to-date node. `RMR_CMD_MAP_GET_VER` and `RMR_CMD_MAP_SET_VER` read and write the version on a storage node. When no session is obviously authoritative — for example after a pserver crash — the client queries every session for its `map_ver` and picks the node with the highest value as the source for the subsequent spread. See [Map Version Handling](../design/dirty-map-versions.md) for the full design.

```{note}
The current `u64` representation of `map_ver` is a temporary choice. It multiplexes ordering, a state-carrying flag (`RMR_STORE_IS_REPLACE`), and peer comparison into a single integer, which does not scale to future needs. A refactor to a richer representation is planned.
```

## Discard coordination

Some failure modes leave the pool with dirty entries for a `member_id` whose underlying data no longer exists — most notably after a disk replacement, where the replaced node returns in a cleared state and the `RMR_STORE_IS_REPLACE` bit is set on its `map_ver`. Such entries have to be discarded across the pool, and the discard must be coordinated so every surviving node processes it before the state is treated as settled.

The client issues a two-step protocol:

1. `RMR_CMD_SEND_DISCARD` to every `NORMAL` session in the pool, identifying the `member_id` whose tracked entries should be dropped.
2. `RMR_CMD_DISCARD_CLEAR_FLAG` once all sessions have acknowledged. This clears the per-member `discard_entries` flag in `pool_md`.

Splitting the exchange in two ensures a surviving node cannot clear its own discard flag before peers have processed the discard. The current trigger is inside the last-IO update: a node whose `map_ver` has `RMR_STORE_IS_REPLACE` set triggers the two-step discard, after which the map spread proceeds.

```{note}
Because Replace is currently disabled (see [Create vs. Assemble](#create-vs-assemble)), the `RMR_STORE_IS_REPLACE` bit is never set in normal operation, so this coordination path is not exercised today. The protocol and handlers are in place for when Replace is re-enabled.
```

## Last-IO reconciliation

If the pserver itself goes down while IOs are in flight, an individual IO may have completed on some storage nodes and not others. No surviving session can be trusted as authoritative on its own.

`rmr_clt_start_last_io_update()` handles this case. It runs from `rmr_clt_pool_try_enable()` when every `member_id` in `pool_md` is present and in `RECONNECTING`:

1. Query each session's `map_ver`; pick the node with the highest value as the authoritative source, applying any pending discards (`RMR_STORE_IS_REPLACE`) first.
2. Spread that map across the pool so every session shares a common baseline.
3. Send `RMR_CMD_LAST_IO_TO_MAP` to every session. Each storage node turns its persisted `last_io` array (the IDs of the most recently processed IOs — see [Terminology](terminology.md), and [Last IO update](../design/last-io-update.md) for the full design) into dirty entries on every peer's map, so any IO that was incomplete at the time of the crash is now marked dirty wherever it could still be missing.
4. Spread the resulting maps again and promote the sessions to `NORMAL`.

## Recovery thread

Lifecycle, map update, discard, and last-IO reconciliation are event-driven — each runs in response to a specific trigger (join, reconnect, replacement, crash). The recovery thread is the part of the control path that runs on its own schedule.

Each client pool has its own recovery worker (`recover_dwork` on `recover_wq` in `rmr_clt_pool`, entry point `recover_work()`) that wakes every `RMR_RECOVER_INTERVAL_MS`. On every tick it walks the pool's sessions and performs three tasks: check whether dirty map entries held on the pserver can be cleared, probe failed sessions to see if IO can resume, and push the latest client-side pool metadata to the storage nodes.

### Map check

When a storage node has gone through an error while IOs are running, dirty entries are added to the map. The map is stored on all storage nodes and on the pserver. As chunks are synced — either through the sync thread or while servicing IOs — the dirty map entries are cleared from the storage nodes. The pserver does not take part in syncing, so it never sees the clears directly; its entries have to be cleared explicitly.

To do that, the recovery worker sends `RMR_CMD_MAP_CHECK` to each storage node for which the pserver still holds dirty entries. The check is only issued for sessions whose `rmr_clt_pool_sess` state is `NORMAL` and whose client-side map is non-empty.

If the storage node's server pool is not itself in the `NORMAL` state, it does not inspect its map and unconditionally replies that the map is non-empty. This prevents the pserver from clearing state against a storage node not yet ready to vouch for it. A `NORMAL` but still-degraded storage node answers honestly — its own map is non-empty and it says so.

After a storage node reports an empty map, the pserver does not clear its entries immediately. It waits for `RMR_MAP_CLEAN_DELAY_MS` and requires the "empty" answer to persist across ticks before unsetting the dirty bits.

`RMR_CMD_MAP_CHECK` is also triggered internally in the reverse direction, from one storage node to another. Each server pool runs its own delayed worker (`clean_dwork` on `clean_wq`, scheduled every `RMR_SRV_CHECK_MAPS_INTERVAL_MS`, entry point `rmr_srv_check_map_clear()`) that walks the dirty maps the node holds for its peers — one map per `member_id` other than its own. For each peer whose map is non-empty, the worker sends `RMR_CMD_MAP_CHECK` to that peer through the attached sync client pool (via `rmr_clt_pool_member_synced()`). If the peer replies that its own map is empty, the storage node clears its local tracking for that peer with `rmr_srv_clear_map()`. The server-side gating rules on the response — `NORMAL`-only inspection, conservative non-empty reply otherwise — apply identically in this direction.

### Store check

When the RMR server gets an error from the backend while sending IOs, it propagates the error to the RMR client and the relevant session moves to `FAILED`. The client stops sending IOs on that session until the error is resolved.

To detect when IO can resume, the recovery worker sends `RMR_CMD_STORE_CHECK` to sessions that are `FAILED` and whose underlying `rmr_clt_sess` is `CONNECTED`. The server queries its backend via `io_store->ops->io_allowed()` — for brmr-server this checks that the block device is both `OPEN` and `MAPPED` — and replies.

A positive response does not put the session back in service directly. It transitions the session from `FAILED` to `RECONNECTING` and calls `rmr_clt_pool_try_enable()`, which drives the map update (or the last-IO update, if all members are reconnecting) that ultimately promotes the session to `NORMAL`. See [Pool and Session States](pool-session-states.md) for the full state machine.

Sessions with `maintenance_mode` set skip the map check but remain eligible for store check and state progression, so they can be brought back online in a controlled way.

### Metadata send

The client pool maintains `pool_md` (see [Terminology](terminology.md)), which the storage nodes read back to assemble or reconcile pool state. At the end of each recovery tick, the worker refreshes the local copy and pushes it to every storage node via `RMR_CMD_SEND_MD_BUF`. A failed send is not retried within the tick — the next tick will try again.
