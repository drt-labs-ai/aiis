# Issue #142 - Search Service Outage (Resolved)

**Date:** 2024-10-15
**Severity:** P1
**Duration:** 47 minutes
**Domain:** Pre-Purchase / Search

## Summary
Search service returned 503 errors for all users due to Solr index corruption during a scheduled reindex.

## Timeline
- 14:22 - Scheduled reindex triggered by deployment pipeline
- 14:28 - Solr JVM heap exhausted, service began returning errors
- 14:35 - Alert fired: SearchServiceAvailability < 50%
- 14:40 - On-call engineer paged
- 14:52 - Reindex cancelled, rollback initiated
- 15:09 - Service restored

## Root Cause
Solr JVM heap was set to 4GB but reindex required 6GB for the product catalog size.

## Resolution
1. Cancelled in-progress reindex
2. Increased Solr JVM heap to 8GB
3. Scheduled reindex during off-peak hours

## Prevention
- Added memory threshold check before reindex
- Implemented graceful degradation (cached results fallback)
- Added capacity planning for product catalog growth
