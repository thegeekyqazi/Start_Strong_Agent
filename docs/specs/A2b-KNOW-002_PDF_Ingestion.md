# A2b-KNOW-002: Bounded PDF ingestion

**Revision:** 1.0

**Owner:** Dev A

**Branch:** `dev-a/a2-know-002-ingestion` (stacked on A2a)

**Engineering/rules:** v1.1 sections 5.1, 10.1, 12.2, 13.2, 19-20; SRC-01/02/03/05/08/09/10 and SEC-01/04/13.

## Contract

An authenticated organization may import strict-base64 PDF bytes within configured byte, page and extracted-character limits. The parser verifies the PDF signature, rejects encryption and malformed input, and stores exact immutable bytes only after parsing succeeds. Each text-bearing page becomes an inert passage with an exact `page:N` locator. Page count, processed coverage, parser version and warnings are persisted and returned.

Pages without extractable text are reported as warnings and make coverage partial. A PDF with no extractable text is rejected with an explicit OCR-required error. OCR is not silently attempted, and imported material remains unverified. Production ingestion remains unavailable until a private object-store and isolated parser-worker deployment are selected.

## Acceptance

- Wrong signature, invalid base64, encryption, oversize input, excess pages/chars and malformed PDFs fail before database evidence records are committed.
- A text PDF preserves exact artifact hash, page count, extracted text and page locators.
- Blank/scanned content is never reported as complete extraction.
- Organization scope and fixture/supplied provenance are server-derived.
