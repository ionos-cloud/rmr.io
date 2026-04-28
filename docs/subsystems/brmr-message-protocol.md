<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# BRMR Message Protocol

BRMR currently has a small set of commands being exchanged between the client and server side. These are map, unmap, and metadata read. These commands use the `rmr_id_t.b` field to inform the server of their presence. This is undesirable because the `rmr_id_t` struct is reserved for use with IOs only. To solve this issue, a proper protocol with command and message structs has been added.

## Message types

BRMR will have 2 message types: Command and IO (used as appropriate). These will be stored in `brmr_msg_hdr.type`.

For the command message type, BRMR will have a struct `brmr_msg_cmd`, which represents all commands. The `cmd_type` field stores which command it is. A union holds structs with command-specific data.

## Command types

The following command types will exist for now (not all are currently used):

`BRMR_CMD_MAP_NEW`    —    Map a new device
`BRMR_CMD_MAP_CHECK`  —    Try to map an already-mapped device
`BRMR_CMD_UNMAP`      —    Unmap a device
`BRMR_CMD_READ_MD`    —    Read metadata
`BRMR_CMD_RSP`        —    Represents a command response (buffer) sent back from the server side

The IO message type is used to send IOs. The message stores fields related to IO, such as flags, sector, and offset. This is not currently used but will be added in the future.
