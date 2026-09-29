# M2-04 — Knowledge layer v0 (schema v3 + ingest + query)

**Status:** done
**Deliverable:** schema v3: `kg_nodes(id, type, ref, attrs_json, case_id, created)`, `kg_edges(src_id, dst_id, rel, attrs_json, created)`, `lessons(id, case_id, kind, text, created)` (§7.1); ingest API: intel commit review → nodes `commit`/`variant`/`hypothesis` + edges `derived_from`; `chromly kg query|neighbors` helpers (surface/function/commit); mọi query log lại (`store/kg_log.jsonl`) — chuẩn bị cho MCP `kg.query` (M4).
**Files:** `chromly/knowledge/__init__.py`, `chromly/knowledge/kg.py`, `chromly/store/db.py` (migration v3), `tests/test_kg.py`, `acceptance/M2-kg.sh`
**Acceptance:** `bash acceptance/M2-kg.sh` → ingest fixture (commit + 2 variants) → query theo commit ra đúng nodes+edges; migration v2→v3 chạy trên DB cũ.
**Evidence:** query output + counts.
**Out of scope:** notebook/digest (M3) · case-close ingest (M4).
**Phụ thuộc:** M2-02.
