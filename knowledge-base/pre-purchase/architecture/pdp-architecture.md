# Product Detail Page (PDP) Architecture

## Overview
The PDP aggregates data from multiple microservices to render product information.

## Data Sources
- **Product Service**: Core product data, descriptions, attributes
- **Price Engine**: Real-time pricing with promotions
- **Inventory Service**: Stock levels and availability
- **Media Service**: Product images and videos
- **Review Service**: Customer ratings and reviews

## Request Flow
```
Browser → CDN → PDP BFF → [Product Service
                          Price Engine
                          Inventory Service
                          Media Service] → Response
```

## Caching Strategy
| Layer | TTL | Invalidation |
|-------|-----|--------------|
| CDN | 60s | On publish |
| BFF | 30s | On price change |
| Product Service | 300s | On product update |

## Key Configuration
- `pdp.cache.ttl.seconds`: CDN TTL (default: 60)
- `pdp.price.refresh.interval`: Price refresh (default: 30s)
- `pdp.inventory.real_time`: Real-time inventory check (default: true)

## Common Failure Modes
1. Price engine timeout → Show last known price with stale indicator
2. Inventory service down → Show "Check availability" CTA
3. Review service down → Hide review section gracefully
