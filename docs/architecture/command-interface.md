<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Command Interface

The RMR command interface provides upper layer clients (e.g. BRMR) a way to send command messages to all storage nodes of an RMR pool, and gives the storage-side handler a way to send a response back. The size of the per-leg response buffer (`size`) is specified by the caller, making it dynamic.

The interface is exposed through `rmr_clt_cmd_with_rsp()` on the client side and `rmr_srv_pool_cmd_with_rsp()` on the server side.

## Buffer allocation

At any point in time the caller does not know how many legs the RMR pool has. Querying first and then calling would create a race window during which the number of legs can change — particularly in setups where legs are added or removed frequently.

The solution is to always allocate for the maximum number of legs (`RMR_POOL_MAX_SESS`, currently 4). The caller allocates a single physically contiguous buffer (`kmalloc`'d — `vmalloc` memory is rejected) of size `RMR_POOL_MAX_SESS * size`. This is a hard requirement: `rmr_clt_cmd_with_rsp()` returns `-EINVAL` if `buf_len != RMR_POOL_MAX_SESS * size`.

RMR divides the buffer into `RMR_POOL_MAX_SESS` slices of `size` bytes, maps each to an sglist, and sends one to each leg. If the pool has fewer than `RMR_POOL_MAX_SESS` legs, the leftover slices are untouched. The server-side handler writes its response into the slice it received. The caller must have a way to distinguish written slices from untouched ones.

The command message itself is passed as an array of kvecs and forwarded to the server side as-is.

## Interaction with map updates

In-flight command requests block map updates until they complete. Callers should be aware that issuing commands during recovery may delay the map update process.

## Sessions that receive commands

Commands are sent to all sessions that are not in FAILED state (CREATED, NORMAL, RECONNECTING, and REMOVING sessions all accept command messages). FAILED sessions are skipped silently, so the caller may receive fewer responses than the total number of legs.

## Error handling

### Error on user level

The server-side handler may fail to execute the command. In this case the error should be encoded in the response buffer and not propagated to RMR. The caller reads it while processing the response slices.

### Error on RMR level

If the command fails in the RMR or RTRS layer (e.g. network failure, memory allocation), the result is reported via the `conf` callback (`rmr_conf_fn`). The errno passed to `conf` has the following encoding:

- `0` — command sent and response received from all legs successfully.
- positive — command failed on some legs. The value is the number of failed legs.
- negative — command failed on all legs. The value is the error code.
