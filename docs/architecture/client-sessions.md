<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Client Sessions

```{image} ../_static/images/architecture/RMR_Arch-Client_1.png
:width: 100%
```

The diagram shows a compute client (`psrv1`) hosting four RMR pools across four storage nodes. Each pool has a replication factor of 2, giving 8 pool sessions in total. Yet only 4 RTRS sessions exist — one per unique storage node.

## Pool sessions and client sessions

RMR separates the concept of a replication leg from the concept of an RTRS connection into two distinct structures.

`rmr_clt_pool_sess` is the replication leg. Each pool has one `pool_sess` per storage node it replicates to. It carries per-pool state: IO routing, dirty map tracking, and session state (NORMAL, FAILED, RECONNECTING, etc.).

`rmr_clt_sess` is the shared RTRS connection to a storage node. It is identified by session name (e.g. `psrv1@rmr-srv1`) and maintained in a global list. A `pool_sess` does not own an RTRS connection directly — it holds a reference to a `clt_sess` and uses it to send IO and command messages.

## Why the split

RTRS pre-allocates and pre-maps memory on the storage server side when a session is established. With a one-pool-one-device design, a compute client hosting many pools would create one RTRS session per pool per storage node. The memory cost on the storage side scales with the number of pools, not the number of storage nodes.

By separating `pool_sess` from `clt_sess`, pools that replicate to the same storage node share a single RTRS session. In the diagram, pools 1 and 3 both have a leg to `rmr-srv1`; they share the `psrv1@rmr-srv1` `clt_sess` and the single RTRS session beneath it. The number of RTRS sessions is bounded by the number of unique storage nodes, not the number of pools.
