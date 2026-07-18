# Returns & Refunds Troubleshooting Guide

## Common Issues

### Return Request Not Processing
**Symptom:** Return request submitted but no confirmation received.
**Root Cause:** Returns service timeout or warehouse connectivity issue.
**Resolution:**
1. Check returns service: `GET /api/returns/health`
2. Verify warehouse API connectivity
3. Review return eligibility rules: `GET /api/returns/policies`
4. Manual process: `POST /api/admin/returns/{id}/process`

### Refund Not Appearing
**Symptom:** Customer says refund not received after 5+ business days.
**Root Cause:** Payment gateway refund failure or bank processing delay.
**Resolution:**
1. Check refund status: `GET /api/refunds/{id}/status`
2. Verify payment gateway refund confirmation
3. Check for partial refund scenarios
4. If gateway confirmed, advise customer to contact bank (3-5 business days)

### Incorrect Refund Amount
**Symptom:** Refund amount doesn't match expectations.
**Root Cause:** Restocking fee applied, partial return not calculated correctly.
**Resolution:**
1. Review refund calculation: `GET /api/refunds/{id}/breakdown`
2. Check restocking fee configuration
3. Verify return policy for product category

## Refund Timeline
- Credit card: 3-5 business days
- PayPal: 1-2 business days
- Gift card: Immediate
- Store credit: Immediate
