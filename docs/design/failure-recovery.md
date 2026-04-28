<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Failure Scenarios and Recoveries

```{contents}
:local:
:depth: 2
```

## Network or IO failure

This error occurs when there is a network disruption between the compute client and one or more storage nodes, or when an IO fails at the backend block device. Both cases lead to the IO failing for that particular session, though at different levels. For a network issue, the failure most likely originates from the RDMA subsystem on the compute client side. For a backend failure, the error originates in the IO store and travels back to the RMR client on the compute client.

Either error triggers a state change in both the RMR client session and the RMR server IO state. All inflight IOs are immediately failed and no further IOs are allowed to that storage node. At this point, the storage node is assumed to have missed some IOs and cannot return to serving IOs until it knows which chunks it missed. Once that information is available, the storage node can serve IOs again. If an IO hits a dirty chunk, that chunk is synced before the IO is served.

When a client session goes to failed state, the RMR client begins tracking the chunk IDs of the IOs it misses. It saves these IDs in its dirty map and sends this information to the storage nodes that are still alive and serving IOs. This replicates the knowledge of dirty chunk IDs. For inflight IOs that failed during the network/IO failure, an explicit map add is sent to the storage nodes for them to save in the dirty map. For subsequent IOs, this information — indicating which storage node is missing the IO — is piggybacked on the IO message itself.

Once the network/IO failure is resolved, the storage node needs to receive the dirty map of all chunk IDs it missed before it can serve IOs again. This happens through the "map update" process, in which the dirty map from a storage node in NORMAL IO state (or from the compute client) is sent to the recovering storage node. In RMR, one absolute truth is maintained: a storage node in NORMAL IO state must have an up-to-date dirty map. At any moment, the current state of dirty chunks can be read from a storage node in NORMAL IO state.

(This absolute truth could be extended to ensure that if the compute client is up and serving IOs, it must also have the updated dirty map. Most of the control path should satisfy this, but it needs a deeper look, testing, and confirmation.)

The map update is triggered from the storage node. It can be triggered automatically by the recovery thread or manually through sysfs. During the entire map update, IOs are frozen to prevent the map from changing while it is being transferred. (In the future this freeze window may be reduced by sending map updates in batches and freezing IOs for the smallest possible batch.) Once the complete dirty map has been sent to the recovering storage node, the session and server IO states are set to allow IO, and the freeze is lifted. The recovering storage node can now serve IOs.

## Storage node crash

This scenario shares similarities with the network/IO failure scenario, mainly in the recovery process. The symptom is the same: the affected storage node misses some IOs.

The key difference is the state awareness of the affected node. After a network/IO failure, the storage node knows it is in a failed state. After a crash and reboot, it does not know whether it is joining an existing pool that has missed IOs or whether a new pool is being created. Because of this, the storage node cannot prevent illegal state transitions such as moving to NORMAL IO state without a map update. The mechanism that handles this is described below.

When a storage node is to be joined to an RMR pool, the user calls `add_sess` from the compute client. This triggers the RMR client to send a `join_pool` message. When the compute client tries to reconnect to a storage node it has lost connection to — whether due to a network disruption or a crash — it sends a `rejoin_pool` message. When a crashed storage node recovers, the RMR client still holds a reference to the previously existing session and automatically sends a `rejoin_pool` message. This rejoin message forces the recovering storage node to recognize that it was part of an existing pool and must go through a map update before serving IOs.

The map update process is the same as described in the "Network or IO failure" section above.

## Compute client crash

See [Last IO update](last-io-update.md).

## Compute client and one or more storage nodes crash

Let's look at more complicated failure scenarios where multiple crashes happen simultaneously or in sequence.

### Storage nodes crash before compute client

Let's take an example setup where a compute client and 3 storage nodes (A, B, and C) are connected. The RMR pool has 3 legs (replication factor 3). Let's say storage node A crashes first. The compute client notices the session state change and begins sending dirty chunk IDs for the missed IOs to storage nodes B and C. Now let's say the compute client crashes. Since only storage nodes B and C were up and serving IOs when the compute client crashed, the `last_io` array for only those 2 nodes is relevant. Their arrays are saved and available when the compute client comes back up and tries recovery.

During recovery from this scenario, if the compute client comes back up first, it goes through the `last_io` update process and brings storage nodes B and C back to NORMAL IO state. When storage node A comes back up, it is simply a matter of performing a map update for it.

If storage node A comes back up first and then the compute client, the compute client will also consider storage node A for `last_io` update. But this changes nothing, because the `last_io` array and dirty map for storage node A are empty after a crash and reboot.

### Compute client crashes before storage node

The scenario where the compute client crashes first while pumping IOs, and then one of the storage nodes crashes, is dangerous and has the potential to cause data inconsistency.

As discussed in the compute client crash scenario, when a compute client crashes while pumping IOs, different IOs may have completed on different storage nodes. This knowledge is stored in the `last_io` array of every storage node. In our example setup (compute client and storage nodes A, B, and C), let's say the compute client crashed while pumping IOs, and an IO touching chunk ID x was written to node A but not to B and C. The `last_io` array of A holds this information. When the compute client comes back up, the `last_io` update process marks chunk ID x as dirty for both nodes B and C, preventing inconsistency.

But let's assume that before the compute client comes back up, storage node A crashes. The `last_io` array is lost. At this point, the data for chunk ID x is inconsistent — a write was performed on node A but not on B and C — and this inconsistency is no longer detectable.

The root cause is that the `last_io` array was stored solely in memory on each storage node, making it a single point of failure.

The solution involves persisting the `last_io` array on non-volatile storage. That storage node crashes would then have no effect on this data. When the compute client comes back, it starts last IO update and restores maps to a consistent state.

