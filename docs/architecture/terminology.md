<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Terminology

RMR stands for Reliable Multicast over RTRS (RDMA transport). Reliable multicast in the networking world provides only "writing" of packets to a group of peers. RMR also provides "reading" of packets from a group of hosts — a reliable read/write multicast group. This section introduces terminology used in the code and documentation of RMR.

## Group

A group of storage servers in a cluster mutually responsible for mirroring data is called a **pool** (also referred to in code and docs as an RMR group, RMG, or RTRS multicast group).

Equivalent concepts in other systems: an MD-RAID+RNBD "configuration" or a DRBD "resource" at the level of hosts.

### pool_name

The name of the pool. Must be ASCII and must match across the compute client and all storage nodes when creating a pool.

### group_id

A `u32` derived as a `jhash()` of the pool name. Used to identify the pool in protocol message headers (`rmr_msg_hdr`). It is computed automatically from the pool name — not set by the user directly.

### member_id

Integer ID for a storage node. Uniquely identifies a particular storage node within a pool. Set by the user when creating a server pool.

## Client-side structures

### rmr_clt_pool

Structure holding client-specific data for a pool. Includes members that hold references for inflight IO tracking, recovery work, IO unit tracking, stats, etc.

A client pool created on the compute client serves IO to and from an upper layer client (BRMR, etc.). A client pool created on a storage node is used by the RMR server pool for syncing data through internal connections to and from other storage nodes. To create such a sync pool, the parameter `sync=y` is used when creating an RMR client pool.

### rmr_clt_sess

Represents an RTRS connection to a storage node. For each RTRS connection opened, RMR maintains one `rmr_clt_sess` in the global `g_sess_list`. Objects are identified by session name in the format `<client-hostname@server-hostname>`.

Multiple pools that replicate to the same storage node share a single `rmr_clt_sess`. See [Client Sessions](client-sessions.md) for details.

### rmr_clt_pool_sess

Represents a replication leg for an RMR pool. An RMR pool with a replication factor of 2 has two `rmr_clt_pool_sess` objects in its session list. Each uses an `rmr_clt_sess` to send IO and command messages over RTRS.

### sessname

User-assigned name for an `rmr_clt_pool_sess`. Can be any string. The in-house convention is `<clt_hostname@server_hostname>`.

### stg_members

An xarray on the pool that maps `member_id` to the corresponding `rmr_clt_pool_sess`. It is the authoritative list of storage members for a pool and is used by the IO path to iterate over members for write replication and dirty map piggyback.

### pool_md

`struct rmr_pool_md` is the pool metadata structure. It holds the persisted description of a pool: pool name, `group_id`, `chunk_size`, `mapped_size`, `queue_depth`, map version, and an `srv_md` array with one entry per storage member. On assemble, the client reads `pool_md` from the server to learn which members belong to the pool and reconstruct dirty maps.

## Server-side structures

### rmr_srv_pool

Structure holding server-specific data for a pool. Includes members that hold references for the sync thread, backend `io_store`, dirty map, `last_io` tracking, and metadata sync work.

### last_io

An array of `rmr_id_t` entries in `rmr_srv_pool`, one slot per queue depth position. Each storage node records the IDs of the most recently processed IOs in this array and persists it to the backend. During recovery, when all sessions are in RECONNECTING state and no authoritative dirty map is available, the client compares `last_io` across storage nodes to determine which node has the most up-to-date data before re-enabling the pool.

### rmr_srv_sess

Server-side representation of an RTRS connection from a compute client or peer storage node. Maintained in the server's global `g_sess_list`.

### rmr_srv_pool_sess

Server-side per-pool session. Tracks the state of a single client connection within the context of a specific server pool. The server-side counterpart to `rmr_clt_pool_sess`.

## Shared concepts

### chunk

The unit of IO tracked by the RMR server pool for dirty IOs. A failed IO dirties the entire chunk, which is then synced in full.

`chunk_size` is configurable at pool creation time. It is a pool-wide parameter and cannot be changed after creation.

On the storage server side, if an IO hits a dirty chunk, the entire chunk is locked and synced from another storage node before the waiting IOs are resumed.

### rmr_srv_req

Every IO results in the creation of an RMR request object (`struct rmr_srv_req`). IOs from the compute client are non-sync IOs and can be reads or writes. IOs from other storage nodes are sync IOs and can only be reads. Sync and non-sync requests are differentiated by flags in the structure.

### dirty map

Each RMR server pool maintains one dirty map per storage member (`struct rmr_dirty_id_map`). The primary storage is a two-level bitmap (`dirty_bitmap[MAX_NO_OF_FLP]`): first-level pages hold pointers to second-level pages, and each second-level page stores one byte per chunk (the least-significant bit marks the chunk dirty). Chunk number is derived directly from the IO offset and `chunk_size_shift`.

`rmr_dirty_id_map` also contains an xarray (`rmr_id_map`) that tracks `rmr_map_entry` objects for chunks currently being actively synced. Each entry carries a reference count (`sync_cnt`) for concurrent sync operations and a wait list for IOs blocked until the sync completes. The xarray entries are keyed by the 128-bit rmr ID (`id.a << 32 | id.b`).

### io_store

`struct rmr_srv_io_store` holds the backend disk information for an RMR server pool. It contains a pointer to the store operations (`brmr_srv_store_ops`) for the registered backend and an opaque private pointer. It is only populated for server pools that have a registered backend.

### queue_depth

The number of I/O requests that can be queued by one RTRS session. A pool-wide parameter set at creation time.
