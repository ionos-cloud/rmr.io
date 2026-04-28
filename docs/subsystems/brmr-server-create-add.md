<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# BRMR server: IO store operations

## Create command

The create command is used to create brmr-server backend store devices. For a pool, it must be called only once — the very first time. For any subsequent operations such as a graceful shutdown and restart, crashes, or failing disks, the add command should be used instead.

The create command expects a clean block device with no old metadata on it. If old metadata is found, the command fails. After this check, the create command registers the block device with the RMR server pool, persists the metadata on the disk, and sets the brmr store state to OPEN.

No parameter check or verification across storage nodes takes place at this step. That is the responsibility of the map command on the brmr-client side (see [BRMR client: map and unmap](brmr-client-map-unmap.md)).

## Add command

The add command is overloaded. It is used both for re-adding a block device that has already gone through a create, and for replacing a broken device with a new one. This distinction is handled internally. Let's look at both scenarios in detail.

### Add after graceful shutdown or crash with intact disk

This scenario covers a graceful pool shutdown and restart, or a storage node crash, where the backend block device is still intact and working. The metadata stored on the block device is intact. The intact metadata also indicates whether the device went through the verification phase, depending on whether the MAPPED flag is set. If the MAPPED flag is set, the disk has already been verified (during a brmr map from the client side) and can immediately start serving IOs.

There is a corner case: a disk belonging to a different pool but with the same name could be re-added, and the add command may pass because the pool name matches. This will be addressed once UUID support is added. It may also require across-storage-node verification even for a simple add.

### Add an empty disk to replace a broken one

This scenario covers a broken backend block device that needs to be replaced with a new one. The empty disk must go through both parameter verification and a sync. The add command handles both internally.

For this case, the user must invoke the add command with `mode=replace`. The brmr-server uses this mode to drive the replace path. The mode is mandatory: an empty disk passed without `mode=replace` is rejected, and a disk that already has metadata passed with `mode=replace` is also rejected. This keeps the on-disk state and the user's intent in sync. In addition to the standard steps (register, write metadata, etc.), this variant does 2 extra things:

When an empty block device is passed with `mode=replace`, the brmr-server must verify that the device parameters (such as `mapped_size`) match those on other storage nodes. This was originally done via the map command from the client side, but the brmr-server can no longer rely on that — there may already be a mapped device on the client side. The brmr-server therefore performs this verification itself. It sends a command to all storage nodes connected through the sync sessions, requesting the parameters of their backend block devices. At least one set of params with the MAPPED flag set (indicating the verification process has been completed) is required.

After verification, the brmr-server informs the RMR server module that this backend block device has no data and needs to be synced. It does this by sending a list of chunk IDs through the RMR server's discard function interface. The RMR server then takes care of syncing the data for the new empty block device.

## Replace command

This use case applies when a user wants to replace an already in-use disk with a completely new one — for example, when the disk is end-of-life or failing a S.M.A.R.T. test.

### Remove the old disk

This step tears down the brmr-srv IO store for the failing disk so a replacement can be added in its place. It is scoped to swapping the backend disk on a single storage node while the storage node itself stays a member of the RMR pool.

The brmr-server exposes two sysfs entries for tearing down a store, and the choice determines what happens to the on-disk metadata:

- `remove_store`: closes the store and unregisters it from the RMR server pool, but leaves the on-disk metadata intact. The same disk can be re-added later (e.g., after a graceful shutdown and restart, or after a transient failure) and will be recognized as a re-add rather than a replace.
- `delete_store` : same teardown, plus zeros the on-disk metadata. The disk is no longer recognizable as a member of the pool; re-adding it would go through the empty-disk replace path.

For the replace flow, `delete_store` is appropriate when the old disk is still readable and you want to wipe it cleanly. `remove_store` is sufficient when the disk is broken or being physically removed, since the new replacement disk will be added with `mode=replace` regardless.

```bash
echo 1 > /sys/class/brmr-server/stores/<pool_name>/remove_store
# or, to also zero the metadata on the old disk:
echo 1 > /sys/class/brmr-server/stores/<pool_name>/delete_store
```

After this, IOs for this leg of the pool will fail because there is no backend disk to service them.

### Add a new disk

Add an empty disk for the same pool. The add command behaves differently for disks with metadata versus disks without metadata.

Use the new (empty) disk and call `add_store` with it for the same pool. (If the disk contains old metadata, clear it first.)

```bash
echo 'device=$device pool=$pool_name mapped_size=$mapped_size mode=replace' > /sys/devices/virtual/brmr-server/ctl/add_store"
```

The `pool_name` and `mapped_size` for this call must match the `create_store` call used when the pool was first created; otherwise the add will fail.

### Sync

Once the add succeeds, trigger the sync thread to sync the entire disk, or simply run IOs.

```bash
echo 'start' > /sys/class/rmr-server/pools/<pool_name>/sync
```

Alternatively, you can skip an explicit sync and let chunks be synced on demand as IOs from the compute client hit them.

## Known issues with brmr-server store

1. The RMR pool name should not be used as an identifier. Since pool names are user-managed, an existing brmr-server store device associated with an RMR pool could be added to the wrong pool if an admin uses the wrong name.

   The planned solution is to internally generate a UUID during the brmr-client map and persist it in metadata, then use it for verification on subsequent adds.
