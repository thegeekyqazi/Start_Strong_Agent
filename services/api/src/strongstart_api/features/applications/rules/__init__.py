"""Deterministic C rules (C2 spec s5; engineering s9.1). Pure functions, no model calls.

Each rule returns findings wrapping the shared ``ValidationResult``. The registry shape
matches s9.1, so the rules can move into A3's common runner at G1 without logic changes.
"""
