# Cart & Checkout Troubleshooting Guide

## Cart Issues

### Items Not Persisting in Cart
**Symptom:** Items added to cart disappear after page refresh.
**Root Cause:** Session management failure or cart service timeout.
**Resolution:**
1. Check cart service health: `GET /api/health/cart`
2. Verify Redis session store connectivity
3. Check `feature.cart.persistence.enabled` flag
4. Review cart service logs for session ID mismatches

### Incorrect Cart Pricing
**Symptom:** Cart shows wrong price, promotions not applied.
**Root Cause:** Promotion engine cache stale, or price engine timeout.
**Resolution:**
1. Flush promotion cache: `POST /api/admin/promotions/flush`
2. Verify price engine: `GET /api/prices/health`
3. Check promotion rule publishing status

## Checkout Issues

### Payment Timeout
**Symptom:** Payment step times out without processing.
**Root Cause:** Payment gateway connection timeout or API key expired.
**Resolution:**
1. Check payment gateway status page
2. Verify API credentials in config: `payment.gateway.api_key`
3. Review timeout settings: `payment.timeout.ms` (default: 30000)
4. Check payment service logs for error codes

### Address Validation Failures
**Symptom:** Valid addresses rejected at checkout.
**Root Cause:** Address validation service degraded.
**Resolution:**
1. Check address service health
2. Temporarily disable strict validation: `checkout.address.strict_validation=false`
3. Contact address service team

## Architecture Notes
- Cart data: Redis (primary) + PostgreSQL (persistence)
- Payment: Stripe/Adyen via payment-service
- Address validation: Google Maps API
