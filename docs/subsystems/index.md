<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Subsystems

```{toctree}
:maxdepth: 1

brmr-client-map-unmap
brmr-message-protocol
brmr-server-create-add
```

BRMR stands for block device over RMR. It uses RMR as its transport layer to send/recv IO (using sg lists).

Using RMR means that the IO that BRMR is sending/receiving is being serviced through more than one storage node (depending on the number of RMR legs). However, BRMR does not always know about this, especially while sending/receiving IOs.

BRMR makes decisions based on the response of each storage node only for commands it sends, not for IOs. An IO serviced from any node is as good as one from any other. This means, however, that it is RMR's responsibility to ensure it services IOs from the node that holds the most up-to-date data.

- **BRMR client** is loaded on the pserver. It uses the rmr-clt module as its transport layer. See [BRMR client: map and unmap](brmr-client-map-unmap.md) for details.
- **BRMR server** is loaded on a storage node. It sits below the rmr-srv module and services IOs. See [BRMR server: IO store operations](brmr-server-create-add.md) for details.
