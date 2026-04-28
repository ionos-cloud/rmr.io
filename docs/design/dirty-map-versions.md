<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Map Version Handling

This page documents how RMR currently tracks map version (`map_ver`) — a single counter that discriminates between dirty-map generations when a pool diverges (session failures, maintenance-mode transitions, store replacements). It is the mechanism that decides which node holds the most up-to-date dirty map after any event that could have left different nodes with inconsistent state.

Dirty maps are maintained by RMR pools to track which chunks need synchronization. Every node tracks the dirty maps of all storage nodes in the pool. Dirty chunks are tracked through a bitmap buffer where each bit represents a chunk number (offset/chunk_size). RMR uses a tree-like structure of memory pages where leaf pages store the actual dirty map data.

RMR currently uses a simple map version scheme, with plans to move to a structured generational history — such as DRBD's Generational Identifiers or a consistent map log.

The [Last IO Update](last-io-update.md) mechanism handles the case where a compute client crashes, restarts, and must reconcile dirty maps across storage nodes. It assumes all storage nodes hold the latest dirty map.

Data inconsistency occurs when a storage node holds an outdated map. To see this in action, consider the following scenario.

A pool with compute client P, connected to two storage nodes A and B.

1. A write succeeds for chunk 2 on both nodes, adding it to the last IO array for both A and B.
2. The connection between the compute client and node A breaks; the `pool_sess` transitions to failed state.
3. Another write comes in for chunk 2, making it dirty for the failed node A. This adds an entry to the map on node B marking chunk 2 as dirty for A. Node A has no knowledge of this write since its connection to the compute client is still down.
4. The compute client crashes and restarts. Network connections between the compute client and all nodes (A and B) are restored.
5. The last IO update is triggered, and the compute client randomly chooses node A to start with.
6. On receiving `RMR_CMD_LAST_IO_TO_MAP`, node A converts last IO entry 2 to be dirty for node B. This happens because node A does not have the updated map from node B, which marks chunk 2 as dirty for A.
7. Node A sends its map to node B. The map on node B now shows chunk 2 as dirty for both A and B. But B's chunk 2 should not be marked dirty as B completed the write on chunk 2.

By introducing map versions, we can solve this problem by finding the map with the highest version among storage nodes before sending `LAST_IO_TO_MAP` commands. If a node was already down when the compute client crashed and therefore carries a stale dirty map, its lower `map_ver` prevents it from being picked as the source.

Let's say B holds the latest map. The compute client would instruct all other nodes to drop their maps and distribute B's map to them — so A now holds the correct map, which marks chunk 2 as dirty for itself.

When the last IO update is triggered and node A receives `RMR_CMD_LAST_IO_TO_MAP`, it tries to convert last IO entry 2, finds it already marked dirty for itself, and skips it. The maps on A and B are now identical.

`map_ver` is an unsigned 64-bit integer but only the lower 63-bit version is monotonic. The most significant bit is an overloaded flag indicating that the storage node's backing store is being replaced — every chunk for that member must be treated as dirty.
