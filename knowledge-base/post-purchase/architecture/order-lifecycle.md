# Order Lifecycle Architecture

## States
```
PLACED → CONFIRMED → PAYMENT_VERIFIED → ALLOCATED → 
PICKED → PACKED → DISPATCHED → DELIVERED → COMPLETED
```

## Error States
- PAYMENT_FAILED
- ALLOCATION_FAILED
- FULFILLMENT_FAILED
- DELIVERY_FAILED
- CANCELLED

## Services Involved

| State Transition | Service | Timeout |
|-----------------|---------|---------|
| PLACED → CONFIRMED | OMS | 30s |
| CONFIRMED → PAYMENT_VERIFIED | Payment Service | 60s |
| PAYMENT_VERIFIED → ALLOCATED | Inventory Service | 120s |
| ALLOCATED → DISPATCHED | Fulfillment Service | async |
| DISPATCHED → DELIVERED | Carrier API | N/A |

## Event Bus
All state transitions publish events to Kafka topic: `order.events`

## Key Config
- `order.payment.timeout.seconds`: 60
- `order.allocation.retry.max`: 3
- `order.fulfillment.sla.hours`: 24
- `notification.shipping.delay.max.minutes`: 30
