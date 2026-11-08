# A2c-KNOW-002: Authorized passage retrieval

**Revision:** 1.0

**Owner:** Dev A

**Branch:** `dev-a/a2-know-002-ingestion` (stacked on A2a/A2b)

**Engineering/rules:** v1.1 sections 5.2, 10.1, 13.2, 14 and 19-20; SRC-01/02/03, APP-05, SEC-01/13.

## Contract

`GET /api/knowledge/retrieve?query=...&limit=...` performs bounded deterministic lexical retrieval over passages belonging to the server-derived organization. It returns exact inert passage text, source/version IDs, locator, hash, provenance and a documented lexical score. Every returned artifact is integrity-verified before disclosure.

Queries are limited to 200 characters and 12 unique lexical tokens. Candidate reads and response counts are bounded; the server configuration may lower a client-requested limit. Unknown, unauthorized and nonmatching passages produce no hits without disclosing which condition applied. Ranking uses token occurrence counts with stable ID tie-breaking. It does not infer truth, resolve conflicting facts or claim semantic similarity.

PostgreSQL lexical retrieval is the required A2 path. Vector reranking is optional and intentionally absent; structured numeric selection remains the typed-fact path.
