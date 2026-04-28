<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Client Session States

```{contents}
:local:
:depth: 2
```


## Introduction

RMR client session states control the behaviour of each `rmr_clt_pool_sess` and are critical
to data integrity. The state governs three things:

1. **Map piggyback**: dirty chunk IDs are piggybacked on write IOs for all sessions that are
   not in NORMAL state. Missing a piggyback entry causes a storage node to miss dirty
   tracking and can lead to data corruption on resync.
2. **IO routing**: IOs are only sent to sessions in NORMAL state. Sessions in any other state
   are skipped and their chunks are piggybacked instead.
3. **Recovery sequencing**: a non-sync session must pass through RECONNECTING and complete a
   map update before reaching NORMAL. Skipping this step risks enabling a storage node that
   has a stale dirty map.

All state transitions go through `pool_sess_change_state()`. The function enforces a strict
set of legal transitions and fires a `WARN_ON` for any illegal attempt. The only legal
transitions are shown in the diagram below.

```{image} ../_static/images/design/IO_perm_states-clt_sess_states.png
:width: 100%
```

> **Note**: the diagram needs updating to reflect the assemble/disassemble paths and
> maintenance mode transitions added after the initial design.

### Legal transitions

| From          | To            | Condition                                      |
|---------------|---------------|------------------------------------------------|
| CREATED       | NORMAL        | Non-sync: manual enable via sysfs; sync: always |
| CREATED       | RECONNECTING  | Non-sync assemble or reconnect path             |
| CREATED       | FAILED        | Link event or IO failure                       |
| CREATED       | REMOVING      | del\_sess called                               |
| NORMAL        | FAILED        | Link event or IO failure                       |
| NORMAL        | RECONNECTING  | Maintenance mode set (`maintenance_mode=true`) |
| NORMAL        | REMOVING      | del\_sess called                               |
| FAILED        | RECONNECTING  | Reconnect succeeded (non-sync only)            |
| FAILED        | NORMAL        | Reconnect succeeded (sync only)                |
| FAILED        | REMOVING      | del\_sess called                               |
| RECONNECTING  | NORMAL        | `rmr_clt_pool_try_enable()` completes recovery |
| RECONNECTING  | FAILED        | Link event or IO failure                       |
| RECONNECTING  | REMOVING      | del\_sess called                               |

REMOVING is a terminal state: no exit transitions are permitted. Any attempt triggers
`WARN_ON`.

A non-sync session going directly from FAILED to NORMAL is an illegal transition and
triggers `WARN_ON`. It must pass through RECONNECTING so that a map update can occur first.
Sync sessions are exempt from this requirement because they do not participate in map
updates and go FAILED → NORMAL directly.

---

## Pool recovery: `rmr_clt_pool_try_enable()`

Pool recovery is centralised in `rmr_clt_pool_try_enable()`. It is called automatically
whenever a session's state changes in a way that could allow recovery to proceed:

- After a successful store check (FAILED → RECONNECTING via `rmr_clt_handle_store_check_rsp`)
- After a successful rejoin (FAILED → RECONNECTING via `rmr_clt_handle_rejoin_rsp`)
- After maintenance mode is unset (`rmr_clt_unset_pool_sess_mm`)
- After an assemble completes (`rmr_clt_process_non_sync_sess`)
- Manually via the `pool_enable` sysfs attribute at the pool level

The function acquires `clt_pool_lock` for its entire duration, serialising concurrent
recovery calls and preventing `rmr_clt_open` from racing with an in-progress recovery.
`rmr_clt_open` uses `mutex_trylock` and returns `-EBUSY` if recovery is running.
`rmr_clt_close` uses a blocking `mutex_lock` and waits for recovery to finish.

### Recovery cases

**Case 1 — ≥1 NORMAL session exists**

The NORMAL session already has a complete, up-to-date dirty map. Freeze IOs, instruct the
NORMAL session to send its map to every RECONNECTING (non-maintenance-mode) session, confirm
each map receipt, then transition all RECONNECTING sessions to NORMAL and unfreeze IOs.

**Case 2 — Exactly one `was_last_authoritative` RECONNECTING session**

`was_last_authoritative` is set by `pool_sess_change_state` on the last non-sync session to
leave NORMAL state when the pool goes fully offline (i.e. when `normal_count` decrements to
zero). It is cleared when the session re-enters NORMAL state.

Because this session held the complete dirty map at the moment the pool went offline, it can
be enabled directly without receiving a map from another node. Send `enable_pool(1)` to the
server, transition the session to NORMAL, then spread its map to any other RECONNECTING
sessions exactly as in Case 1.

**Cases 3/4 — All pool\_md members present and RECONNECTING**

No NORMAL session exists and no session carries `was_last_authoritative` (the pool went
offline before any session had a chance to set the flag, or all sessions failed
simultaneously). Run `rmr_clt_start_last_io_update()` to determine which storage node has
the most recent data, resync the divergent nodes, then transition all RECONNECTING sessions
to NORMAL.

If not all pool\_md members are yet RECONNECTING (some are still FAILED or not yet
assembled), the function returns without action and waits to be called again when the next
session reaches RECONNECTING.

### `was_last_authoritative` and `normal_count`

`normal_count` is an atomic counter on the pool that tracks how many non-sync sessions are
currently in NORMAL state. It is maintained inside `pool_sess_change_state`:

- Incremented when any non-sync session enters NORMAL.
- Decremented (with `atomic_dec_and_test`) when a non-sync NORMAL session transitions to
  FAILED, or to RECONNECTING due to maintenance mode. If the decrement reaches zero the
  transitioning session is marked `was_last_authoritative = true`.
- Decremented (plain `atomic_dec`) when a non-sync NORMAL session transitions to REMOVING.

Sync sessions are excluded from `normal_count` entirely because they do not carry
authoritative dirty maps.

---

## States

### RMR\_CLT\_POOL\_SESS\_CREATED

A newly created (non-sync) session enters CREATED after a successful `join_pool` exchange
with the server. The session has a live RTRS connection but is not yet ready for IOs.

What happens next depends on the `add_sess` mode:

- **create mode**: the session stays in CREATED. The user must manually write `1` to the
  per-session `enable` sysfs entry. This sends `enable_pool(1)` to the server and
  transitions the session to NORMAL.
- **assemble mode**: `rmr_clt_process_non_sync_sess` reads the full `pool_md` from the
  server's on-disk metadata, creates dirty maps for all known members, broadcasts a
  `POOL_INFO_ASSEMBLE` to peers, then transitions the session to RECONNECTING and calls
  `rmr_clt_pool_try_enable()` to attempt immediate recovery.

A sync session skips both paths and goes directly to NORMAL after `join_pool`.

#### IO and command behaviour

No IOs are sent to this session.
Dirty map entries are piggybacked for this member on IOs to other sessions.
Command messages can be sent.

---

### RMR\_CLT\_POOL\_SESS\_NORMAL

A non-sync session reaches NORMAL via one of:

1. **Manual enable (create mode)**: user writes to the per-session `enable` sysfs entry
   while the session is in CREATED state.
2. **`rmr_clt_pool_try_enable()` Case 1**: a NORMAL session spread its map to this
   RECONNECTING session and confirmed receipt.
3. **`rmr_clt_pool_try_enable()` Case 2**: this session carried `was_last_authoritative`
   and was enabled directly.
4. **`rmr_clt_pool_try_enable()` Cases 3/4**: all members were RECONNECTING; a
   `last_io_update` resync completed.

A sync session reaches NORMAL after creation and again after a successful rejoin.

On every RECONNECTING → NORMAL transition `was_last_authoritative` is cleared.

#### IO and command behaviour

IOs are sent to this session.
Dirty map entries are **not** piggybacked (the storage node is up to date).
Command messages can be sent.

---

### RMR\_CLT\_POOL\_SESS\_FAILED

A session enters FAILED when:

- The RTRS link event reports a disconnect.
- An IO to this session fails.

On every NORMAL → FAILED transition `pool->map_ver` is incremented so that in-flight IOs
carry the new version and the server can detect the change.

A FAILED session is excluded from IO routing. Its member ID is piggybacked on every write
so that other storage nodes accumulate dirty entries on its behalf. Command messages cannot
be sent because the RTRS connection is down.

When the RTRS connection is re-established, a store check is sent automatically. A
successful response triggers FAILED → RECONNECTING and calls `rmr_clt_pool_try_enable()`.

#### IO and command behaviour

No IOs are sent.
Dirty map entries are piggybacked for this member.
No command messages can be sent.

---

### RMR\_CLT\_POOL\_SESS\_RECONNECTING

A non-sync session enters RECONNECTING when:

- A successful reconnect (store check response) arrives while the session is in FAILED or
  CREATED state.
- The session was just created with `add_sess mode=assemble`.
- A user manually writes `enable=0`, which then sets maintenance mode on a non-REMOVING session (`rmr_clt_set_pool_sess_mm`).

**Sync sessions must not enter RECONNECTING** (enforced by `WARN_ON` in
`pool_sess_change_state`). Sync sessions do not participate in map updates; they go
FAILED → NORMAL directly.

A RECONNECTING session is still excluded from IO routing. Its member ID continues to be
piggybacked on writes so dirty entries keep accumulating. Command messages can be sent,
which is required for the MAP\_READY / MAP\_SEND / MAP\_DONE exchange that happens during
recovery.

Transition to NORMAL happens exclusively through `rmr_clt_pool_try_enable()`. There is no
manual map update path; calling `pool_enable` via sysfs invokes the same function.

#### Maintenance mode

Setting maintenance mode (`enable=0` on a NORMAL session) transitions the session to
RECONNECTING with `maintenance_mode=true`. While in maintenance mode the session is
excluded from IO routing and from recovery: `rmr_clt_pool_try_enable()` skips
maintenance-mode sessions when scanning for candidates.

Clearing maintenance mode (`enable=1`) sends `enable_pool(1)` to the server, clears
`maintenance_mode`, and immediately calls `rmr_clt_pool_try_enable()`. If the session was
`was_last_authoritative` it is picked up as the Case 2 auth session; otherwise recovery
proceeds through Cases 1, 3, or 4 as normal.

#### IO and command behaviour

No IOs are sent.
Dirty map entries are piggybacked for this member.
Command messages can be sent.

---

### RMR\_CLT\_POOL\_SESS\_REMOVING

A session enters REMOVING when `del_sess` is called, regardless of its current state.
REMOVING is a terminal state: `pool_sess_change_state` fires `WARN_ON` if any transition
out of REMOVING is attempted.

On entering REMOVING, IOs are frozen and the session is erased from `stg_members` so that
the IO piggyback loop stops referencing it. A `leave_pool` message is sent to the server.
Depending on the del\_sess mode:

- **delete**: the dirty map and `pool_md.srv_md` entry for this member are removed. The
  member is gone permanently.
- **disassemble**: the dirty map is preserved so that the piggyback loop on remaining
  sessions continues to accumulate dirty entries for this member until it reassembles.
  The `pool_md.srv_md` entry is also preserved so that `rmr_clt_pool_try_enable()` can
  wait for this member on reassembly. If this was the last non-sync session, all maps are
  deleted (they will be recreated from `pool_md` on the first assemble).

After the REMOVING state is reached the session object is freed.

#### IO and command behaviour

No IOs are sent.
No dirty map entries are piggybacked.
Command messages can be sent (for the `leave_pool` exchange).
