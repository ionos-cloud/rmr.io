<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# One Pool One Device

```{contents}
:local:
:depth: 2
```

In RMR, a pool is scoped to a single mapped block device. Replicating multiple devices on the same compute client therefore uses multiple RMR pools — one per device — even when those pools all connect to the same set of storage nodes. The cost is bounded: pools connecting to the same storage node share a single RTRS session, so the network footprint scales with the number of unique storage nodes, not with the number of devices. See [Client Sessions](../architecture/client-sessions.md) for the structural split (`rmr_clt_pool_sess` per leg, `rmr_clt_sess` per RTRS connection) that enables this sharing.

## Properties of the model

- **No cross-device coupling.** A network or backend failure on one device's pool does not affect any other device's pool. Each pool is an independent object with its own state, dirty maps, and recovery work.
- **Per-device leg manipulation.** Adding or removing a `rmr_clt_pool_sess` leg on a pool changes replication for exactly one device. Migrating a device to a new storage node is straightforward — add a leg on the new node, let it sync, remove the leg on the old node — and does not disturb replication for any other device.
- **Per-device replication topology.** Replication factor and the set of storage nodes are chosen independently per device.
- **Single-device dirty map.** A server pool's dirty map tracks chunks for one device. There is no device dimension to disambiguate; chunks are identified by chunk number alone.

## Implementation

- **BRMR client.** `brmr_clt_map_device()` calls `brmr_clt_create_pool()`, which calls `rmr_clt_open()` once per BRMR pool. Each device is mapped through its own BRMR pool with a unique pool name. The block-device tag set, request queue, and refcount all live on the BRMR pool struct.
- **BRMR server.** Each `brmr_srv_blk_dev` is bound to one `rmr_pool` via its `pool` field. Backend store registration is therefore one-to-one with an RMR server pool.
- **Dirty map.** `struct rmr_dirty_id_map` is held per pool and per peer member, indexed by `member_id`. There is no device key.

The one-to-one binding is enforced at the BRMR layer's user-facing flow rather than by an explicit kernel-level check. The BRMR pool struct retains some legacy fields (a per-pool device list and a shared tag set) from the earlier multi-device-per-pool design, but `brmr_clt_map_device()` always creates a fresh pool for each call and never reuses an existing one. These fields will be investigated and removed in the future if they are not needed for the one-pool-one-device model.

## Vestiges of the original multi-device design

The original RMR design considered carrying multiple devices in a single pool, with IOs differentiated by a 128-bit identifier `rmr_id_t = (u64 a, u64 b)` — one field would have carried a device ID. To keep an error on one device from disrupting others within the shared session, that direction also envisioned **channels**: per-device control planes inside a single RMR session.

Channels were never built, and there are no remnants of them in the code today. The 128-bit `rmr_id_t`, however, is still around. It has been **repurposed**, not retired:

- `id.b` is the starting chunk number for an IO.
- `id.a` is the count of consecutive chunks the IO touches, starting at `id.b`. See `rmr_map_calc_chunk()` in `rmr/rmr-map.c` for the encoding.

`id.a` is currently constrained to `1` — the client IO submission path enforces this with `BUG_ON(id.a > 1)` in `rmr/rmr-clt.c`. Parts of the multi-chunk infrastructure are already in place (`rmr_map_calc_chunk()` computes the count, and dirty-map iteration loops in `rmr-map.c` already iterate over `id.a` chunks), but the sync/wait-list interaction needed for IOs that span multiple chunks has not been worked out.

The two-`u64` identifier is wider than the current model strictly needs. The `id.a` / `id.b` split is planned to be removed once the multi-chunk picture is settled, in favour of a single chunk-number field. No concrete refactor is staged in the code yet.
