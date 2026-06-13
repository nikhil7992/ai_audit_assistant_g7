# API Endpoints Summary

The Expense Audit service exposes a single FastAPI gateway that orchestrates four internal microservices.

## Base URL

| Environment | URL |
|-------------|-----|
| Dev | `http://<ALB_DNS_DEV>` |
| Prod | `https://<ALB_DNS_PROD>` |

## Endpoint groups

| Group | Prefix | Purpose |
|-------|--------|---------|
| Health | `/health` | Readiness and liveness probes |
| Audit | `/audit/*` | Full document ingestion and audit pipeline |
| Validate | `/validate` | Single-expense policy compliance check |
| Policies | `/policies/*` | Semantic search over the policy knowledge base |
| Reports | `/reports/*` | Retrieve stored audit report results |

## Authentication

All endpoints are protected by ALB listener rules. Internal service-to-service calls use IAM task role credentials via ECS metadata.
