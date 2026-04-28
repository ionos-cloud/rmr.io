<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Data Path

## Client Side IO Path

- Write requests are sent to all sessions which are in NORMAL state.

NORMAL state is the RMR representation of a healthy storage server which is capable of serving IOs. A healthy storage server is one which has no unsynced/dirty data, or one which knows which portions or chunks are to be synced. This is tracked through the dirty map.

- Read requests are sent to sessions in NORMAL state, in a round robin manner.
- Write requests are completed if it completes for at least one session. Although the RMR client waits to get responses for all sessions, success or failure.
- For failed write requests, a map_add is sent to all storage nodes in NORMAL state.
- The map_add info for subsequent write requests are piggy-backed with the write IO message.

## Server Side IO Path

- Check if the storage server is healthy to service IOs.
- Check if the data chunk corresponding to the IO request is dirty.
- If they are dirty:
  - If the chunk is not syncing already, mark the chunk as syncing and create a sync request.
  - If the chunk is syncing, add the IO request to the “wait list”.
  - On sync completion, process IO requests from “wait list”.
- If they are not dirty, send the request down to the BRMR-server.


```{image} ../_static/images/architecture/rmr_io_req-IO_path_server_side.png
:width: 100%
```

### Flow for sync request

Besides syncing data chunks when an IO arrives for it, RMR-server also runs a sync thread in the background which synchronizes the dirty data. It also locks the chunks while data is syncing, so that all incoming IO goes to the “wait list”.

## Data model
*Planned — not yet documented.*