<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Sync Thread

## Usage

The sync process can be triggered as follows:

```
$ echo "start" > /sys/class/rmr-server/pools/<pool_name>/sync
```

A running sync process can be stopped altogether:

```
$ echo "stop" > /sys/class/rmr-server/pools/<pool_name>/sync
```

This sync process iterates over the dirty chunks of the RMR pool and syncs them one by one.

## Working

The workings of the sync thread are simple. A `thread_state` param tracks whether a sync thread is already running or stopped. There can only be a single sync thread running for a pool.

A sync thread's job is to sync data across storage nodes without the involvement of the compute client. The sync thread must be started on the storage node that is out of sync. Therefore the IOs over the network that the sync thread generates are always read IOs only.

A sync thread can only be started when the server pool state is NORMAL, since this indicates that the storage node has an updated map and can send IOs to the backend.

The sync thread picks up dirty entries from the map one by one and creates sync requests for them. These sync requests perform remote reads and writes the data to the local backend.

At any point in time, the number of inflight sync requests is bounded by the `sync_queue_depth` module parameter of `rmr-server` (default: 32, range: 1–512). The effective depth is further capped at the pool's `queue_depth` to avoid exceeding RTRS permit limits. Tuning this value controls the trade-off between sync throughput and the impact on IO from the compute client.

(Sync request flow is described in [Data Path](data-path.md))
## Failure cases

When a single sync request fails to complete, the sync thread fails that request and exits. To continue syncing, the underlying error must be resolved and the sync thread must be started again with `echo "start"`.

The sync thread can fail if the pool state changes from NORMAL to NO_IO.
