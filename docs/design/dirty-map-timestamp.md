<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Dirty Map Timestamp

```{contents}
:local:
:depth: 2
```


The dirty maps are maintained on both compute clients and storage servers. When a dirty chunk on a certain storage node is synced, an `RMR_MSG_MAP_CLEAR` message is sent to other storage nodes so that they can clear this dirty map entry, and then the dirty map entry for that synced chunk is removed from that storage node. In this process, the dirty entry for that synced chunk is cleared from the storage nodes but NOT from the compute client.

Clearing the dirty map from the compute client happens all in one go. For this, the `recover_work` sends an `RMR_CMD_MAP_CHECK` command to all storage nodes whose pool\_session connection is in NORMAL state. If a storage node responds that it has no dirty map, the compute client can delete the dirty map of that storage node. But there can be a race condition where the storage node responds that its map is clear, but a write IO failed for that storage node and a new dirty entry was just added to the local dirty map at the compute client. To avoid this, whenever a dirty entry is added to the map, the timestamp (`map->ts`) is updated. The response of the `RMR_CMD_MAP_CHECK` command is accepted only if `map->ts` is `RMR_MAP_CLEAN_DELAY_MS` old. This creates a wide enough window to safely confirm that no new dirty entry has been added since the storage node sent its response.

The question is whether this time window is sufficient. Let's see what needs to happen for the race condition to delete legitimate dirty entries even with a 5-second delay window.

```
recover_work                               write IO  
-------------------------------------------------------------------
Sends RMR_CMD_MAP_CHECK  
to sess1 (NORMAL)  
  
Receives response from storage1  
that it has no dirty map entries  
  
At rmr_clt_handle_map_check_rsp()  
before the map->ts check.  
  
                                            Write IO failed  
                                            Updates map->ts  
                                            Adds dirty map entry  
  
(time-gap)  
  
map->ts check fails,  
dirty map does NOT get cleared
```

The time gap shown above must be greater than 5 seconds for `map->ts` to fail and clear legitimate dirty entries.

One last thing to note: what happens if the `map->ts` check passes and then the `recover_work` path gets preempted? Would a failed IO add a dirty map entry that then gets removed once `rmr_clt_handle_map_check_rsp()` resumes? This may require a lock for the dirty map itself.
