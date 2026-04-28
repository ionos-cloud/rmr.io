<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Motivation

This project consists of two kernel modules. Namely, BRMR and RMR. Together they provide a new replication solution in the Linux kernel. It would be a block level, active-active replication solution for RDMA transport.

The existing block level replication solution in the Linux kernel is DRBD, which is an active-passive solution. The data replication in DRBD happens through 2 network hops.

Another block level active-active solution which one can build is by exporting block devices, either through NVMeOF or RNBD/RTRS, over the network, and then creating a RAID1 device over it. It would provide a single hop replication solution, but the synchronization during a degraded state goes through 2 hops.

BRMR+RMR provide an active-active single hop replication, controlled by the client side RMR modules. It also provides single hop (re)synchronization, by reading missed IOs directly between storage nodes. This results in faster recovery, reduced latency due to reduced hops, and utilizes less resources on the client side. The latter part is important for hyperscalers who sell the client side resources like CPU and memory.

Reliable Multicast over RTRS (RMR) uses the existing RTRS kernel module in the RDMA subsystem. RMR works in a client-server architecture, with the server module residing on the storage nodes. RMR uses the transport ULP RTRS to guarantee delivery of IO to a group of hosts; and also provides data recovery if one host in the group misses some IOs. The data recovery is handled by the RMR server module, directly between the storage nodes.

BRMR is a network block device over RMR. BRMR provides mirroring functionality and supports replacement of disks.

RMR tracks dirty IOs through a dirty map, and has internal mechanisms to prevent data corruption in case of crashes, similar to the activity log in DRBD.

## Why a new kernel module, and why separate ones

The active-active one-hop replication and one-hop synchronization feature could have been added to an existing block level replication solution (DRBD). But we chose to develop new kernel modules from scratch because of two main reasons.

1) We wanted to keep the "single-hop replication and syncing" RDMA transport offering in a separate kernel module (RMR). RMR is designed in such a way that it can be used by any other solution for reliably sending data in the form of sg lists over the RDMA network, with a guarantee of eventual consistency.
2) We think that DRBD’s core abstractions (per‑node peer replication, single lower device) are orthogonal to “active-active replication” model.

## Using BRMR for block-level replication

The simplest way to use RMR is through BRMR, which exposes a `/dev/brmrX` block device backed by an RMR pool. Any application that needs replicated block storage -- virtual machine disks, databases, filesystems -- can use the BRMR block device directly without any awareness of the replication underneath. This covers most traditional storage use cases.

## Using RMR directly for flexible replication

BRMR maps one block device to one RMR pool. This is sufficient when the data model is a flat block address space, but some systems need more flexibility. RMR's client interface (`rmr_clt_request`) accepts arbitrary scatter-gather lists and delivers them to a group of storage nodes over RDMA. It does not impose any structure on the data. This makes RMR usable as a replication transport for systems whose data model goes beyond a single block device.

For example, an object storage system like Ceph could use RMR pools to replicate object data across storage nodes, while keeping its own control plane for placement and cluster management. Similarly, distributed key-value stores, log-based streaming systems, or tiered storage architectures could each use RMR pools to reliably deliver data to the appropriate group of nodes.
