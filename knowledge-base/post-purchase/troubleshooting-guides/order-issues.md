# Order Management Troubleshooting Guide

## Common Order Problems

### Order Stuck in Processing
**Symptom:** Order remains in "Processing" status for > 30 minutes.
**Root Cause:** OMS workflow stuck, or fulfillment service timeout.
**Resolution:**
1. Check OMS workflow status: `GET /api/orders/{id}/workflow`
2. Review fulfillment service health
3. Manually advance workflow: `POST /api/admin/orders/{id}/advance`
4. Check for database deadlocks in OMS logs

### Order Confirmation Email Not Sent
**Symptom:** Customer did not receive order confirmation.
**Root Cause:** Notification service failure or email queue backlog.
**Resolution:**
1. Check notification service: `GET /api/notifications/health`
2. Check email queue depth in RabbitMQ console
3. Manually trigger confirmation: `POST /api/admin/notifications/resend`
4. Verify customer email address in order

### Incorrect Order Total
**Symptom:** Order total doesn't match expected amount.
**Root Cause:** Tax calculation error or promotion applied incorrectly.
**Resolution:**
1. Review order calculation audit trail: `GET /api/orders/{id}/audit`
2. Check tax service configuration for customer region
3. Verify promotion codes used during checkout

## Architecture
- OMS: SAP Order Management
- Fulfillment: Custom microservice
- Notifications: Event-driven via RabbitMQ
