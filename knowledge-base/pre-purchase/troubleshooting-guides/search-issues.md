# Search Issues Troubleshooting Guide

## Common Search Problems

### Empty Search Results
**Symptom:** Users see no results for valid search queries.
**Root Cause:** Often caused by Solr index corruption or reindex in progress.
**Resolution:**
1. Check Solr health at `/solr/admin/cores`
2. Verify product index status
3. Trigger manual reindex if needed: `POST /api/admin/search/reindex`
4. Clear search cache: `POST /api/admin/cache/clear?type=search`

### Slow Search Response
**Symptom:** Search responses take > 3 seconds.
**Root Cause:** Missing Solr cache warm-up, connection pool exhaustion.
**Resolution:**
1. Check Solr query cache hit ratio (target: > 70%)
2. Review connection pool settings: `search.connection.pool.size`
3. Enable query result caching for faceted search

### Incorrect Product Ordering
**Symptom:** Products appear in wrong order, relevance seems off.
**Root Cause:** Boost rules misconfigured or stale merchandising rules.
**Resolution:**
1. Review boost rules in the Merchandising console
2. Check `search.boost.configuration` feature flag
3. Re-publish merchandising rules

## Search Architecture
- Frontend → Search Service → Solr
- Cache layer: Redis (TTL: 300s)
- Fallback: Elasticsearch for full-text
