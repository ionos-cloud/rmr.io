<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Maintenance Mode

```{contents}
:local:
:depth: 2
```


RMR's maintenance mode is a way to disable one leg (a storage node) of an RMR pool for IOs. Once in maintenance mode, the RMR client on the compute client side makes sure not to send IOs to that storage node. However, it may exchange mgmt messages.

Maintenance mode is applied to an entire leg of the RMR pool (RAID leg). This means that from the client side, the RMR client pool session goes into maintenance mode, which is reflected in its state. In addition, the storage node connected to that pool session also goes into maintenance mode. Apart from the maintenance mode status, the actual states of both the RMR client pool session and the storage node are also affected. This is done to enforce restrictions like "No IO should be sent".

The RMR client pool session goes into RECONNECTING state to indicate that the network is fine but a map\_update is required before IOs can be serviced. This type of RMR client pool session state overloading is also used when a backend device failure occurs.

The storage node goes into "NO IO" state, to denote that IOs cannot be serviced.

During maintenance mode,

- No IOs are sent to that storage node.
- Operations like map\_update are not allowed.
- Mgmt messages are allowed and may be exchanged internally.

Since it is guaranteed that no IOs are sent to the storage node, no IOs are sent down to the backend device. This creates a safe window to perform operations like removing or replacing the backend disks.

The RMR server pool on the storage node can also be worked upon once in maintenance mode. Operations like removing and reconnecting sync sessions, deleting and recreating the RMR client sync pool, can be performed. A complete reboot and recreation of the RMR server node is also possible.

## How to set and unset maintenance mode

To set a leg into maintenance mode, do the following.

```bash
$ echo '0' > /sys/devices/virtual/rmr-client/pools/<pool_name>/sessions/<session_name>/enable
```

To bring a leg out of maintenance mode, do the following.

```bash
$ echo '1' > /sys/devices/virtual/rmr-client/pools/<pool_name>/sessions/<session_name>/enable
```

## Checking maintenance mode

To check if an RMR client pool session is in maintenance mode, do the following:

```bash
$ cat /sys/class/rmr-client/pools/test_pool/sessions/psrv0@stg-rmr0/state
reconnecting
Maintenance mode: 1
```

To check if a storage node is in maintenance mode, do the following:

```bash
$ cat /sys/class/rmr-server/pools/test_pool/state
no_io
Maintenance mode: 1
```

## What happens in maintenance mode

When a storage node is in maintenance mode, it means that it will be missing IOs during that period. It has different consequences for read and write IOs in this case.

For Read IOs, since one leg of RAID is missing, the performance would drop.

For write IOs, since the storage node is missing them, they need to be tracked in the form of dirty map entries. This tracking happens at both the compute client and the other active (NORMAL state) storage nodes. When the user unsets maintenance mode for that storage node, RMR first performs a map\_update internally so that the storage node learns which write IOs it missed and which chunks are dirty for its backend device.

While putting a storage node in maintenance mode, to make sure that all the storage nodes and the compute client have a consistent picture (in terms of which IOs are sent), IOs are frozen for a short while on the compute client side. This makes sure that the state of the session and the storage node is consistent among all the IOs and the other sessions.