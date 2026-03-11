# Remediation Runbook

---

## NODE_DEGRADATION

### Immediate Triage
1. Confirm which node is affected: check `controller_vm_cpu_pct` and `storage_write_latency_ms` per node
2. SSH to the CVM on the affected node and run `top` to identify CPU consumers
3. Check storage controller logs: `cvm> nutanix_smart_stats` or equivalent for hardware errors

### Isolation
4. Live-migrate VMs off the degraded node to healthy nodes (vMotion / AHV live migration)
5. Once VMs are evacuated, put the node into maintenance mode to prevent new VM placement

### Recovery
6. If disk errors are present: identify the failing disk via `smartctl -a /dev/sdX` and schedule replacement
7. If CVM is crashing: restart the CVM (`genesis stop cvm; genesis start cvm`)
8. Re-run storage health check after CVM restart to confirm replication is healthy

### Post-Incident
9. After hardware replacement, re-add the node to the cluster and confirm storage re-replication completes
10. Verify `replication_lag_ms` returns to <5ms before closing the incident

---

## NOISY_NEIGHBOR

### Immediate Triage
1. Identify the noisy VM: on the affected node, run `esxtop` (VMware) or `virsh domstats` (KVM) to find the top CPU/IOPS consumer
2. Confirm which VM is responsible for the IOPS spike

### Isolation
3. Apply a CPU/IOPS limit on the noisy VM using the hypervisor's resource controls (VMware: `Shares`, `Limit`, `Reservation`)
4. If the workload is legitimate but unexpected (e.g., backup job): coordinate with the application team to reschedule to off-hours

### Recovery
5. Optionally live-migrate the noisy VM to a less-utilized node
6. Monitor `cpu_usage_pct` and `storage_read_iops` to confirm they return to baseline

### Post-Incident
7. Implement proactive IOPS limits on high-risk VMs (databases, batch processors)
8. Review VM placement policy to ensure large workloads are distributed across nodes

---

## STORAGE_REBALANCE

### Immediate Triage
1. Confirm this is a rebalance (not a failure): all nodes should show elevated `disk_throughput_mbps` simultaneously
2. Check if a node was recently added/removed or if scheduled maintenance triggered the rebalance

### Isolation
3. This is expected behavior — no isolation required. However, if performance impact is severe:
4. Throttle the rebalance operation via the cluster management UI or CLI (reduces background I/O priority)

### Recovery
5. Wait for rebalance to complete. Monitor `disk_throughput_mbps` returning to baseline (typically 30–90 minutes)
6. Confirm `replication_lag_ms` drops back to <5ms after completion

### Post-Incident
7. Schedule future node additions/removals during maintenance windows
8. Consider increasing network bandwidth (LACP bonding, 25GbE upgrade) if rebalance events cause unacceptable performance degradation

---

## MEMORY_PRESSURE

### Immediate Triage
1. Identify which VMs are consuming the most memory on the affected nodes
2. Check if balloon drivers are active: VMware `esxtop` → `M` view; AHV: `virsh domstats --balloon`
3. Determine if this is workload growth or a memory leak (compare with historical baselines)

### Isolation
4. Evacuate low-priority VMs from affected nodes to relieve pressure
5. For leaking VMs: coordinate with application team to restart the offending service or VM

### Recovery
6. If memory growth is legitimate: add RAM to the physical nodes or expand the cluster
7. Apply memory reservations to critical VMs to prevent balloon driver from stealing their memory

### Post-Incident
8. Set memory alerts at 75% utilization for proactive capacity planning
9. Review VM memory configurations — right-size VMs that are over-provisioned to free capacity

---

## NETWORK_SATURATION

### Immediate Triage
1. Identify the traffic source: check which VMs or processes are generating high throughput (use `iftop` or `nethogs` on the hypervisor)
2. Common culprits: backup jobs, live VM migrations, large VM deployments, distributed application replication

### Isolation
3. Pause or throttle the high-bandwidth operation (e.g., pause backup job, limit live migration bandwidth)
4. If caused by a legitimate workload: schedule it to off-peak hours

### Recovery
5. Monitor `network_rx_mbps` and `network_tx_mbps` returning to normal
6. Confirm `replication_lag_ms` drops below 10ms after traffic normalizes

### Post-Incident
7. Implement QoS policies to reserve minimum bandwidth for storage replication traffic
8. Segregate storage replication traffic onto a dedicated VLAN or physical NIC
9. Upgrade network infrastructure if saturation is occurring regularly under normal load

---

## DISK_PRE_FAILURE

### Immediate Triage
1. Identify the failing disk: run `smartctl -a /dev/sdX` for all disks on the affected node; look for reallocated sectors, pending sectors, and uncorrectable errors
2. Check the storage controller log for SCSI sense errors or ATA error logs

### Isolation
3. Immediately initiate a proactive data migration: mark the disk as "to be removed" in the cluster management UI
4. The cluster will begin re-replicating all data from that disk to other disks/nodes
5. Do NOT wait for the disk to fail completely — DISK_PRE_FAILURE window is your recovery window

### Recovery
6. Once data migration completes (all blocks reprotected), physically replace the disk
7. Re-add the replacement disk to the storage pool
8. Verify storage health shows RF2 compliant (no degraded objects)

### Post-Incident
9. Set up automated SMART monitoring alerts
10. Review disk age across the cluster — if one disk is failing due to age, peer disks from the same purchase batch may fail soon

---

## CASCADING_FAILURE

### Immediate Triage
1. Identify Phase 1 (degraded node) vs Phase 2 (rebalance on healthy nodes)
2. Focus recovery effort on the Phase 1 node first — stabilizing or evacuating it stops the cascade

### Isolation
3. Follow NODE_DEGRADATION isolation steps for the primary failing node
4. Do NOT perform any additional maintenance on other nodes while the cascade is active — this can break RF2 redundancy

### Recovery
5. Once the primary node is stable or evacuated, monitor Phase 2 rebalance completing automatically
6. Confirm `replication_lag_ms` and `disk_throughput_mbps` return to baseline on all nodes

### Post-Incident
7. Run a full cluster health check after the incident: confirm all data has RF2 protection
8. Review whether the cluster has sufficient spare capacity to absorb a node failure — rule of thumb is N+1 headroom (cluster should function at N-1 nodes with <70% resource utilization)
9. Consider adding a spare node or increasing the replication factor to RF3 for critical workloads
