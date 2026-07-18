# Issue #289 - Mass Shipping Notification Delay (Resolved)

**Date:** 2024-11-08
**Severity:** P2
**Duration:** 3 hours
**Domain:** Post-Purchase / Shipping

## Summary
Shipping notification emails were delayed by 3+ hours due to RabbitMQ message queue backup.

## Timeline
- 09:00 - Black Friday traffic spike began
- 09:45 - RabbitMQ queue depth exceeded 50,000 messages
- 10:15 - Notification service consumer lag > 30 minutes
- 10:30 - Alert: NotificationDelay P2
- 11:00 - Scaled notification consumers from 3 to 12 pods
- 12:00 - Queue depth returning to normal
- 13:00 - All notifications sent, queue cleared

## Root Cause
Notification consumer pods were not configured to auto-scale during high-throughput events.

## Resolution
1. Manually scaled consumer pods
2. Implemented HPA (Horizontal Pod Autoscaler) for notification consumers
3. Set queue depth alert threshold to 10,000

## Prevention
- HPA configured: min=3, max=20 pods based on queue depth
- Pre-scaling runbook created for known high-traffic events
- Added queue depth to Black Friday readiness checklist
