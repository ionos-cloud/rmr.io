<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Removal of a Storage from RMR Pool

```{contents}
:local:
:depth: 2
```

Gracefully removing a storage node from an RMR pool aims to keep both the pool and the storage being removed in a good and healthy state during and after the removal. This page covers the `delete` flow: permanently removing a storage node from an RMR pool. The replication factor of the pool is reduced by one, the leg is decommissioned, its on-disk pool metadata is wiped at the brmr-store layer, and the compute client and all remaining peers erase the state they held for it. The storage node returns to a clean slate, so the disk can be reformatted and reused with `create_store` in any pool.

The flow is triggered from the compute client with:

```bash
echo 'mode=delete' > /sys/class/rmr-client/pools/<pool_name>/sessions/<session_name>/del_sess
```

`del_sess` accepts two modes, and they are not interchangeable:

- `mode=delete`: permanent removal. Pool members drop the storage from their dirty maps and member lists; the storage zeros its on-disk pool metadata and exits the pool. **This page describes this flow.**
- `mode=disassemble`: temporary removal. The storage leaves the pool but keeps its on-disk pool metadata so it can rejoin later via `add_sess mode=assemble`. The pool's effective replication factor is unchanged once the leg comes back. Not covered here.

For a side-by-side comparison of the two modes, see [Delete vs. Disassemble](../architecture/control-path.md#delete-vs-disassemble) in Control Path.

Two related workflows are also out of scope:

- Remove and add back: temporarily detaching a leg. Built from `del_sess mode=disassemble` followed by `add_sess mode=assemble`, not from `mode=delete`.
- Extend: adding a new leg to an existing pool. Uses `add_sess mode=assemble` directly.

## Removal steps

Delete is divided into three steps. Steps 1 and 2 both involve network messages and can fail; step 3 is local bookkeeping.

### Step 1: Exclude from IO

On triggering `del_sess mode=delete`, the pool session transitions to `REMOVING`. From this point the storage node is excluded from all future IOs.

The compute client then briefly freezes the pool, waits for inflight IOs to drain, removes the member from `stg_members`, and unfreezes. A `RMR_CMD_LEAVE_POOL` with `delete=true` is sent to the departing node. The server there processes the leave (`rmr_srv_process_leave_delete()`) by deleting the dirty maps it held for every *other* member — it no longer needs to track dirty data destined for anyone — and transitions its server pool back to `REGISTERED` if a backend store is still attached, or `EMPTY` if it has been unregistered.

`REMOVING` is a terminal state on the client side. There is no way to revert to `NORMAL`; the only way to bring the leg back is to fully remove it and add it as a new leg via `add_sess`. Even if a later step fails, the storage will not participate in IOs or in `POOL_INFO` propagation again — `rmr_clt_send_pool_info()` skips sessions in `REMOVING` (and `FAILED`).

### Step 2: Remove dirty map state across the pool

Once the departing node is out of the IO path, its tracked dirty state must be erased everywhere else so that no party keeps tracking writes for a storage that is no longer part of the pool.

- On the compute client's pool, the map for the departing member is removed and the corresponding `srv_md` slot in `pool_md` is zeroed.
- A `RMR_CMD_POOL_INFO` with `REMOVE` + `DELETE` is sent to every remaining peer. Each peer runs `rmr_srv_delete_store_member()`, which erases the departing member's `stg_members` entry and dirty map.

These messages cross the network and can fail. On failure, removal halts: the departing session remains in `REMOVING` and is not rejoined. The user must resolve the underlying issue and retrigger `del_sess`. The handler is written so that steps that have already succeeded are idempotent when replayed.

### Step 3: Free session structures

With map state consistent across the pool, the last step is purely local: the session is detached from the pool's session list, its sysfs directory is destroyed, the `rmr_clt_pool_sess` is freed, and the reference on the underlying `rmr_clt_sess` is put. At this point the removal from the compute client side is complete.

## State after removal

### On the compute client (RMR client)

- No dirty entries for the removed storage on any map.
- No `rmr_clt_pool_sess`, no session sysfs directory.
- `pool_md.srv_md` slot for that member is zeroed; `stg_members` no longer contains it.

### On the removed storage node

- Dirty maps for all other members have been deleted by `rmr_srv_process_leave_delete()`. The map for this node's own `member_id` is retained while the backend store is still registered — it belongs to the pool definition, not to any leg.
- The server pool state is `REGISTERED` while the backend store remains attached, and transitions to `EMPTY` once `delete_store` unregisters the store. It does **not** go to `NORMAL` or `CREATED`.
- After `delete_store`, the on-disk pool metadata on the backend block device is wiped. The disk must be reformatted with `create_store` before it can be used in any pool again.

### On other storages in the pool

- `POOL_INFO REMOVE + DELETE` has erased the departing member's `stg_members` entry and dirty map on each peer.
- No dirty entries for the removed storage remain anywhere in the pool.

## Further steps required by the user

`del_sess mode=delete` on the compute client handles the bulk of the work, but the internal sync sessions between storage nodes are not torn down automatically. Each storage node holding a sync session to (or from) the departing node must run `del_sess mode=delete` on that sync session explicitly.

For a sync client pool's `del_sess`, only steps 1 and 3 are executed. Step 2 is skipped because a sync client pool does not maintain per-member dirty maps, and the storage node the sync client points at has already had its tracking erased when delete was triggered from the compute client.

## Use cases

- **Migrating a backend store from one machine to another.** Add the new store on the new machine as an additional leg via `add_sess`, complete the data sync — preferably via the sync thread — until the dirty map drains, then delete the old leg with `del_sess mode=delete` from the compute client.
- **Reducing the replication factor.** A user who originally configured replication across *n* storage nodes and later wants to reduce *n* can remove surplus legs one at a time, each with `del_sess mode=delete`.
