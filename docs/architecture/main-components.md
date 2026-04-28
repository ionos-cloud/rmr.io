<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Modules and Components

An RMR group is composed of the non-sync client pool instance on compute client, the sync client pool instance and the server pool instance on storage servers. These instances connect through RTRS sessions to take the shape of an RMR pool. Due to this structure, RMR-client modules are loaded on all nodes and RMR-server modules are loaded on the storage servers.

BRMR provides virtual block devices on the client side through the BRMR-client module. The IOs are passed onto RMR. On the server side, BRMR-server module receives the IOs and passes them to the backend device (ANDBD block devices, scsi devices, etc). BRMR-server module provides features like disk replacement, partial data discard, and also provides metadata service for RMR (for storing bitmap).

RMR modules consists of:

1. RMR-client
   - Creates and removes pools.
   - Adds sessions which correspond to replication factors (raid1).
   - Sends IO requests to the RMR servers.
     - Replicated write requests on compute clients (non-sync sessions).
     - Remotely read from between the RMR servers (sync sessions).
   - Sends and receives commands to and from RMR servers for pool management.
2. RMR-server
   - Creates and removes pools.
   - Receives IO requests and transfers to BRMR-server.
   - Handles commands from the RMR client, covering add_sess, map updates, etc.
   - Tracks dirty chunks resulted from failed write requests.
   - Controls the synchronization process.
   - Send reads requests to other servers as part of data synchronization.
3. BRMR-client
   - Maps and unmaps BRMR block device.
   - Interfaces with the block layer, to receive the IOs and pass it down to the rmr-client pool, to be serviced.
   - Uses the rmr-client command interface to send/recv mgmt commands (like map/unmap) to and from storage servers, through the rmr-client pool.
4. BRMR-server
   - Creates/Adds/Removes backend device stores.
   - Allows the backend device to register to an RMR server pool. This allows it to receive IOs and commands from BRMR-client.
   - Provides APIs to submit IOs to the block layer of the kernel, and check if the store is ready to accept IOs.
