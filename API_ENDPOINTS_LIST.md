# API Endpoints List

Complete list of all REST API endpoints exposed by the Expense Audit service.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check |
| POST | `/audit/upload` | Upload PDF/JSON expense documents and run full pipeline |
| POST | `/audit/sample` | Run audit on pre-loaded synthetic sample data |
| POST | `/validate` | Validate a single expense object against policy |
| POST | `/policies/query` | Semantic search over the OpenSearch policy index |
| GET | `/reports` | List all stored audit reports |
| GET | `/reports/{reportId}` | Fetch a single audit report by ID |

See [API_ENDPOINTS_QUICK_REFERENCE.md](./API_ENDPOINTS_QUICK_REFERENCE.md) for curl examples.
See [API_ENDPOINTS_SUMMARY.md](./API_ENDPOINTS_SUMMARY.md) for a high-level overview.
