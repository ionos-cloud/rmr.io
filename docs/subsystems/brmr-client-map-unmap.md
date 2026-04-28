<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# BRMR client: map and unmap

A BRMR map is performed on the brmr-client side. It uses the RMR client pool and tries to map the block device at the end of the RMR sessions for that pool. The management commands are exchanged between the brmr-client where the map command was triggered and the brmr-server at the backend of the RMR server for every storage node connected to the RMR pool. This means that the brmr-client communicates with the brmr-server modules of all storage nodes connected as legs for that RMR pool.

A BRMR map is the client counterpart of the create/add commands on the brmr-server (see [BRMR server: create and add store](brmr-server-create-add.md)). There is a slight difference: on the brmr-server side, the user uses create or add depending on whether the device is being created for the first time or re-added after a graceful removal. On the brmr-client side, there is only the map command. This is acceptable because from a user's perspective there is no difference between a map for a newly created device and a re-added one. However, there are differences in error handling and device parameter handling that are managed internally by the brmr-client code. These special cases and their reasons are discussed below.

Internally, a BRMR map can be divided into 2 categories. The special cases and how they are handled are also discussed for each category. The identification and handling of these 2 cases are done entirely internally.

## First-time map for a block device

This corresponds to the "create" case on the brmr-server side. For this kind of map, the brmr-client must communicate with the brmr-server on every storage node connected to that RMR pool. If even one returns a failure or is unreachable, the map cannot proceed. The reason is discussed below.

The brmr-client starts by reading the metadata (which contains the device params) from the devices on each storage node. This is done to compare and verify that the devices across storage nodes do not have conflicting parameters. Once this comparison is successful, a map command is sent to all storage nodes. The brmr-server on each storage node processes this command and sets the device store to MAPPED state. This state is also persisted in the device metadata. The MAPPED state indicates that the device has gone through a parameter check across the storage nodes that are part of the same RMR pool to which the device's brmr-server store is registered.

There is currently some ambiguity around the MAPPED state:

- Does MAPPED mean the device is currently BRMR-mapped? If so, an unmap should clear it and update the metadata (it is not cleared at present).
- Or does MAPPED mean the device has passed its first-time parameter check? If so, could a device with MAPPED set be removed and re-added to a different pool with the same name?

The second issue can be solved by using a UUID for the brmr-store. Correspondingly, during an unmap, this state is unset and the metadata is updated.

One of the conditions a BRMR map checks is whether all reachable devices are either all mapped or all unmapped. A mixture of mapped and unmapped devices reachable from the same RMR pool indicates an error state.

- All devices unmapped: this is a fresh map.
- All devices mapped: this occurs when the pserver has gone through a crash and reboot, and a BRMR map is attempted for a device for which all storage nodes are up and running.

The MAPPED state also helps with crash scenarios. If a storage node that was part of an RMR pool with a mapped brmr-client device crashes and comes back up, re-adding the device through brmr-server does not require any new BRMR map call or parameter verification across storage nodes, because the MAPPED state is read from the metadata and restored. This means the user must be careful when re-adding the device — adding it to the wrong pool would cause data inconsistency. This is mitigated by requiring unique pool names. (Once UUID support is implemented, parameter verification across storage nodes can be done by default for every type of add.)

### First-time map (device just created)

A map for a device just created on the brmr-server side. The device is going through its first map and expects a clean disk (no data).

A device being created for the first time must complete a successful series of steps on all storage nodes (legs). This is required because brmr needs to verify device parameters across all storage nodes (such as size and block size). Failing to do this during the first create would require remembering which node failed the parameter check, which becomes complex when combined with future failure scenarios.

After the steps complete successfully, the params are saved to the devices on all participating storage nodes. These saved params are used later for future re-maps and device re-adds. The re-add (which uses the add command) with an empty disk is used when adding a new leg or replacing a broken device on the brmr-server side (see [BRMR server: IO store operations](brmr-server-create-add.md)).

### Re-map after crash or graceful shutdown

A map for a device that has been re-added — the device has been through a map before, either via a graceful unmap or after a crash on the client side.

For a re-map, some nodes can be allowed to fail because they can be re-added later. Parameter verification is not needed because it was already done during the first map. However, a mixture of nodes — some with a mapped device and some with an unmapped (never-mapped) device — is not allowed. This is because the mapped device may have serviced IOs, and an unmapped device would not have received that data.

## Unmap

*Planned — not yet documented.*
