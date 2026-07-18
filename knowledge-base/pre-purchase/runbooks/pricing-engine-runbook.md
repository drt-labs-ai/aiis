# Pricing Engine Runbook

## Overview
The pricing engine calculates final product prices including base price, discounts, promotions, and tax.

## SLAs
- P99 latency: < 200ms
- Availability: 99.9%
- Cache hit ratio: > 85%

## Escalation Path
1. L1: Clear cache and restart pricing service
2. L2: Rollback to last stable config
3. L3: Engage pricing team (pricing-team@company.com)

## Common Operations

### Flush Pricing Cache
```bash
curl -X POST http://pricing-service/admin/cache/flush \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Check Pricing Rules Status
```bash
curl http://pricing-service/admin/rules/status
```

### Roll Back Pricing Config
```bash
kubectl rollout undo deployment/pricing-service -n commerce
```

## Monitoring
- Grafana dashboard: `/d/pricing-engine`
- Alert: PricingLatencyHigh (> 500ms for 5 min)
- Alert: PricingErrorRate (> 1% for 2 min)
