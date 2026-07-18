# Fulfillment Service Runbook

## Overview
The fulfillment service manages the lifecycle of order fulfillment from confirmation to shipment.

## SLAs
- Order processing: < 2 hours
- Fulfillment confirmation: < 24 hours
- Shipment notification: < 30 minutes after dispatch

## Common Operations

### Check Fulfillment Queue
```bash
curl http://fulfillment-service/admin/queue/status
# Returns: pending, processing, failed counts
```

### Retry Failed Fulfillments
```bash
curl -X POST http://fulfillment-service/admin/retry-failed \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"max_age_hours": 24}'
```

### Emergency Warehouse Switch
If primary warehouse is down:
```bash
kubectl set env deployment/fulfillment-service \
  WAREHOUSE_ENDPOINT=https://backup-warehouse.internal \
  -n commerce
```

## Monitoring
- Grafana: `/d/fulfillment-service`
- Alert: FulfillmentQueueDepth > 1000
- Alert: FulfillmentErrorRate > 5%

## Escalation
1. L1: Retry failed items, check warehouse connectivity
2. L2: Switch to backup warehouse
3. L3: Engage fulfillment team + logistics partner
