# API Endpoints Quick Reference

Replace `<BASE_URL>` with your ALB DNS name or local address.

## Health check

```bash
curl http://<BASE_URL>/health
```

## Upload and audit

```bash
curl -X POST http://<BASE_URL>/audit/upload \
  -F "files=@invoice.pdf" \
  -F "files=@receipt.json"
```

## Run sample audit

```bash
curl -X POST http://<BASE_URL>/audit/sample
```

## Validate single expense

```bash
curl -X POST http://<BASE_URL>/validate \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "TEST-001",
    "vendor": "Marriott Chicago",
    "category": "accommodation",
    "amount": 450.00,
    "date": "2026-05-15",
    "description": "Hotel 2 nights"
  }'
```

## Query policies

```bash
curl -X POST http://<BASE_URL>/policies/query \
  -H "Content-Type: application/json" \
  -d '{"query": "hotel nightly rate limit", "top_k": 5}'
```

## List reports

```bash
curl http://<BASE_URL>/reports
```

## Get report by ID

```bash
curl http://<BASE_URL>/reports/BATCH-20260603-120000
```
