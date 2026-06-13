# Expense Audit

AI-powered corporate expense audit platform.
Infrastructure in **AWS CDK v2 (TypeScript)** · Business logic in **Python (FastAPI)** · CI/CD via **GitHub Actions + STS OIDC**.

---

## Project structure

```
expense-audit/
├── .github/
│   └── workflows/
│       └── deploy-dev.yml              # CI/CD pipeline — 4 jobs, us-east-1 only
│
├── app/                                # Python business logic layer
│   ├── src/
│   │   ├── main.py                     # FastAPI entry point
│   │   ├── config/
│   │   │   └── settings.py             # All env-var backed config
│   │   ├── api/
│   │   │   └── routes.py               # All HTTP route handlers
│   │   ├── agents/
│   │   │   ├── ocr_agent.py            # AWS Textract extraction
│   │   │   ├── validation_agent.py     # Bedrock LLM + OpenSearch RAG
│   │   │   ├── duplicate_agent.py      # Titan embeddings + SHA-256
│   │   │   └── audit_agent.py          # Report synthesis + S3 persist
│   │   ├── data/
│   │   │   ├── fake_gen.py             # Stdlib-only fake data generator (no Faker)
│   │   │   ├── generate_policies.py    # 12 corporate policy documents
│   │   │   ├── generate_synthetic_data.py  # 18 synthetic expense scenarios
│   │   │   └── seed_opensearch.py      # Chunk + embed + index policies
│   │   └── utils/
│   │       ├── bedrock_client.py       # Bedrock LLM + Titan embed wrapper
│   │       └── opensearch_client.py    # k-NN policy store
│   ├── tests/
│   │   └── test_agents.py             # Unit tests covering agents + data layer
│   ├── Dockerfile
│   └── requirements.txt
│
├── cdk/
│   ├── expense-audit-ecr-repository-stack/   # Stack 1 — ECR repos
│   │   ├── bin/ecr-repository-app.ts
│   │   ├── lib/expense-audit-ecr-repository-stack.ts
│   │   ├── package.json · tsconfig.json · cdk.json
│   │
│   └── expense-audit-app-stack/              # Stack 2 — ECS Fargate + infra
│       ├── bin/app-stack-app.ts
│       ├── lib/expense-audit-app-stack.ts
│       ├── package.json · tsconfig.json · cdk.json
│
├── .editorconfig · .gitattributes · .gitignore · .npmrc
├── api-endpoints.json
├── API_ENDPOINTS_LIST.md · API_ENDPOINTS_QUICK_REFERENCE.md · API_ENDPOINTS_SUMMARY.md
├── catalog-info.yaml
└── README.md
```

---

## Architecture — single region (us-east-1)

```
Internet
    │
    ▼
Application Load Balancer (us-east-1, port 80)
    │
    ▼
ECS Fargate — ExpenseAuditCluster (private subnets)
    │
    ├── expense-audit-gateway  :8000   FastAPI orchestrator
    │       │
    │       ├─→ expense-audit-ocr        :8001   AWS Textract
    │       ├─→ expense-audit-validation :8002   Bedrock + OpenSearch
    │       ├─→ expense-audit-duplicate  :8003   Titan embeddings
    │       └─→ expense-audit-audit      :8004   Bedrock + S3
    │
    ├── Amazon OpenSearch Service    k-NN policy index (1024-dim Titan)
    ├── Amazon Bedrock               Claude (LLM) + Titan (embeddings)
    ├── AWS Textract                 Document OCR
    ├── Amazon S3 — reports bucket   Audit report JSON storage
    └── Amazon S3 — docs bucket      Textract upload staging (7-day TTL)
```

---

## Synthetic dataset — complete data folder

The `src/data/` layer produces the exact folder structure shown in the reference
images. Call `POST /admin/generate-data` after first deploy to write all files.

### Data folder layout (matches images exactly)

```
app/data/
├── generate_synthetic_data.py    25 KB — produces invoices/, forms/, ocr_output/
├── generate_policies.py          18 KB — produces policies/
│
├── forms/                        4 forms × (JSON + PDF) = 8 files
│   ├── FORM-001-ALICE.json       ground-truth sidecar (2 KB)
│   ├── FORM-001-ALICE.pdf        rendered reimbursement form (4 KB)
│   ├── FORM-002-BOB.json / .pdf
│   ├── FORM-003-CAROL.json / .pdf
│   └── FORM-004-DAVID.json / .pdf
│
├── invoices/                     14 invoices × (JSON + PDF) = 28 files
│   ├── INV-AIR-001.json / .pdf
│   ├── INV-DUP-COPY-001.json / .pdf
│   ├── INV-DUP-NEAR-001.json / .pdf
│   ├── INV-DUP-ORIG-001.json / .pdf
│   ├── INV-HIGH-VALUE-001.json / .pdf
│   ├── INV-HOTEL-001.json / .pdf
│   ├── INV-HOTEL-VIOL-001.json / .pdf
│   ├── INV-LATE-001.json / .pdf
│   ├── INV-MEAL-001.json / .pdf
│   ├── INV-MEAL-VIOL-001.json / .pdf
│   ├── INV-PROHIBIT-001.json / .pdf
│   ├── INV-SUPPLY-001.json / .pdf
│   ├── INV-TECH-001.json / .pdf
│   └── INV-TRANS-001.json / .pdf
│
├── ocr_output/                   18 _ocr.json stubs (1 per document)
│   ├── FORM-001-ALICE_ocr.json
│   ├── FORM-002-BOB_ocr.json
│   ├── FORM-003-CAROL_ocr.json
│   ├── FORM-004-DAVID_ocr.json
│   ├── INV-AIR-001_ocr.json
│   ├── INV-DUP-COPY-001_ocr.json
│   ├── INV-DUP-NEAR-001_ocr.json
│   ├── INV-DUP-ORIG-001_ocr.json
│   ├── INV-HIGH-VALUE-001_ocr.json
│   ├── INV-HOTEL-001_ocr.json
│   ├── INV-HOTEL-VIOL-001_ocr.json
│   ├── INV-LATE-001_ocr.json
│   ├── INV-MEAL-001_ocr.json
│   ├── INV-MEAL-VIOL-001_ocr.json
│   ├── INV-PROHIBIT-001_ocr.json
│   ├── INV-SUPPLY-001_ocr.json
│   ├── INV-TECH-001_ocr.json
│   └── INV-TRANS-001_ocr.json
│
└── policies/                     12 .txt files (2 KB each)
    ├── PP-001_Vendor_Gifts.txt
    ├── PP-002_Office_Supplies.txt
    ├── TP-001_Air_Travel.txt
    ├── TP-002_Hotel_Accommodation.txt
    ├── TP-003_Meals_Entertainment.txt
    ├── TP-004_Ground_Transportation.txt
    ├── TP-005_Technology_Equipment.txt
    ├── TP-006_Submission_Deadlines.txt
    ├── TP-007_Prohibited_Expenses.txt
    ├── TP-008_Approval_Thresholds.txt
    ├── TP-009_Duplicate_Fraud_Prevention.txt
    └── TP-010_International_Travel.txt
```

### Four named employees (same as v1)

| Employee | ID | Department | Manager |
|---|---|---|---|
| Alice Johnson | EMP-1001 | Sales | Sarah Chen |
| Bob Martinez | EMP-1002 | Marketing | Tom Wilson |
| Carol Lee | EMP-1003 | Engineering | Jake Peters |
| David Kim | EMP-1004 | Finance | Lisa Nguyen |

### 14 invoice + 4 form scenarios

| ID | Employee | Scenario | Expected | Policy |
|---|---|---|---|---|
| INV-HOTEL-001 | Alice Johnson | clean | COMPLIANT | TP-002 |
| INV-AIR-001 | Bob Martinez | clean | COMPLIANT | TP-001 |
| INV-MEAL-001 | Carol Lee | clean | COMPLIANT | TP-003 |
| INV-TRANS-001 | David Kim | clean | COMPLIANT | TP-004 |
| INV-TECH-001 | Alice Johnson | clean | COMPLIANT | TP-005 |
| INV-SUPPLY-001 | Bob Martinez | clean | COMPLIANT | PP-002 |
| INV-HOTEL-VIOL-001 | Bob Martinez | violation | VIOLATION | TP-002 — Ritz $650 > $350 NYC limit |
| INV-MEAL-VIOL-001 | Alice Johnson | violation | VIOLATION | TP-003 — Nobu $211/person > $100 cap |
| INV-PROHIBIT-001 | Carol Lee | violation | CRITICAL | TP-007 — spa is absolute prohibition |
| INV-HIGH-VALUE-001 | David Kim | violation | VIOLATION | TP-008 — $6,499 > $5,000 CFO threshold |
| INV-LATE-001 | Alice Johnson | violation | PENDING_REVIEW | TP-006 — 55 days past deadline |
| INV-DUP-ORIG-001 | Carol Lee | duplicate | COMPLIANT | TP-009 — original |
| INV-DUP-COPY-001 | Carol Lee | duplicate | EXACT_DUPLICATE | TP-009 — SHA-256 match |
| INV-DUP-NEAR-001 | Carol Lee | duplicate | NEAR_DUPLICATE | TP-009 — $257.50 / +1 day |
| FORM-001-ALICE | Alice Johnson | clean | COMPLIANT | multiple |
| FORM-002-BOB | Bob Martinez | violation | VIOLATION | TP-002, TP-003 |
| FORM-003-CAROL | Carol Lee | duplicate | NEAR_DUPLICATE | TP-009 |
| FORM-004-DAVID | David Kim | violation | VIOLATION | TP-007, TP-008 |

### Three runtime data paths

```
Path A — POST /audit/sample  (no upload, no OCR)
─────────────────────────────────────────────────
generate_all_samples()
    returns {"expenses": [...], "invoice_ids": [...], ...}
                │
                ▼
ValidationAgent.validate(expense)          per expense
    query = category + vendor + amount + description
    OpenSearch k-NN  →  top-5 policy chunks
    Bedrock Claude  →  compliance_status + confidence_score
                │
                ▼
DuplicateAgent.detect(expenses)            full batch
    SHA-256 fingerprint  →  exact matches
    Bedrock Titan embeddings  →  near-duplicates
                │
                ▼
AuditAgent.generate_report(...)
    Bedrock Claude  →  executive summary
    Persist JSON  →  S3 reports bucket
                │
    returns AuditReport JSON


Path B — POST /audit/upload  with .json sidecar files
──────────────────────────────────────────────────────
Client uploads INV-HOTEL-001.json
                │
OcrAgent.extract_bytes(content, "INV-HOTEL-001.json")
    detects .json extension
    _parse_sidecar(raw_dict)   →  confidence = 1.0  (no Textract cost)
    writes INV-HOTEL-001_ocr.json to ocr_output/
                │
ValidationAgent → DuplicateAgent → AuditAgent  (identical to Path A)


Path C — POST /audit/upload  with .pdf files
─────────────────────────────────────────────
Client uploads INV-HOTEL-001.pdf
                │
OcrAgent.extract_bytes(content, "INV-HOTEL-001.pdf")
    uploads to S3 docs bucket
    AWS Textract AnalyzeDocument (FORMS + TABLES features)
    parses key-value pairs + table cells  →  confidence 0.80-0.95
    writes INV-HOTEL-001_ocr.json to ocr_output/
                │
ValidationAgent → DuplicateAgent → AuditAgent  (identical to Path A)
```

The `ocr_output/` stubs are pre-seeded from ground-truth by `generate_all_samples()`
so the complete data folder is available for offline inspection and CI without
needing live AWS services.

### Policy seeding flow

```
POST /admin/seed-policies
    │
generate_policy_files(data/policies/)   writes 12 .txt files
    │
_split_into_chunks()    300-word windows, 50-word overlap
    │
BedrockClient.embed_text()   Amazon Titan Embed Text v2 (1024-dim)
    │
OpenSearchPolicyStore.index_policies()   upsert into k-NN index
    │
returns { policy_files:12, total_chunks:~48, indexed:~48 }


At validation time (per expense):
    query = "Hotel Marriott $650.00 NYC 2-night stay"
    OpenSearch k-NN  →  top-5 most similar policy chunks
    Bedrock Claude receives chunks as context
    →  { compliance_status, violations, confidence_score, reasoning }
```

### Expected `/audit/sample` output

| Metric | Expected value |
|---|---|
| Compliance score | ~20-35 / 100 |
| Overall verdict | ESCALATED |
| Total claimed | ~$10,500 |
| Policy violations found | 7-9 |
| Duplicate pairs | 2 (1 exact + 1 near) |
| CFO approval required | Yes (INV-HIGH-VALUE-001 + FORM-004-DAVID) |
| Aggregate confidence | 0.85-0.92 |
---

## CI/CD pipeline — job sequence

```
push to feature/**
        │
        ▼
[Job 1] deploy-expense-audit-ecr-stack
        CDK deploys ECR repo to us-east-1
        (uses CDK_ROLE_ARN via OIDC)
        │
        ▼
[Job 2] build-and-publish
        docker build ./app
        → push to ECR us-east-1 (:latest + :$GITHUB_SHA)
        → upload image.tar as artifact
        │
        ▼
[Job 3] deploy-expense-audit-app-cdk
        CDK deploys ECS Fargate + ALB + OpenSearch + S3 + IAM
        (passes imageTag=$GITHUB_SHA via CDK context)
        │
        ▼
[Job 4] force-update-ecs
        aws ecs update-service --force-new-deployment
        (ECS pulls new image from ECR, rolling update)
```

All jobs use the same `CDK_ROLE_ARN` secret. The role is assumed via OIDC — no long-lived AWS keys stored in GitHub.

---

## Placeholders — fill these before deploying

### GitHub repository secrets

Go to **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value | Used by |
|---|---|---|
| `CDK_ROLE_ARN` | `arn:aws:iam::<ACCOUNT_ID>:role/cdk-deploy-role` | All 4 jobs |

### GitHub Actions workflow

| Location | Placeholder | Replace with |
|---|---|---|
| `env.ECR_REPOSITORY` | `<YOUR_GITHUB_ORG>/expense-audit` | Your GitHub org, e.g. `myorg/expense-audit` |

### SSM parameters (set before `cdk deploy`)

```bash
aws ssm put-parameter \
  --name "/dev/expense-audit/opensearch-endpoint" \
  --value "https://search-YOUR-DOMAIN.us-east-1.es.amazonaws.com" \
  --type String --region us-east-1

aws ssm put-parameter \
  --name "/dev/expense-audit/opensearch-password" \
  --value "YOUR_STRONG_PASSWORD" \
  --type SecureString --region us-east-1
```

### Application environment variables

All values marked `# PLACEHOLDER` in `app/src/config/settings.py`:

| Variable | Description |
|---|---|
| `AWS_ACCOUNT_ID` | 12-digit AWS account ID |
| `TEXTRACT_S3_BUCKET` | S3 bucket for Textract document uploads |
| `OPENSEARCH_ENDPOINT` | Full HTTPS OpenSearch domain URL |
| `OPENSEARCH_PASSWORD` | OpenSearch master password |
| `REPORTS_S3_BUCKET` | S3 bucket for audit report storage |

### catalog-info.yaml

| Field | Replace with |
|---|---|
| `github.com/project-slug` | `<YOUR_GITHUB_ORG>/expense-audit` |
| `spec.owner` | Your Backstage team name |

---

## Setting up OIDC trust (one-time, per account)

```bash
# Step 1 — Create OIDC provider
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com" \
  --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1"

# Step 2 — Create the CDK deploy role (replace placeholders)
ACCOUNT_ID="<YOUR_ACCOUNT_ID>"
GITHUB_ORG="<YOUR_GITHUB_ORG>"
REPO_NAME="expense-audit"

cat > trust-policy.json << TRUST
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:${GITHUB_ORG}/${REPO_NAME}:*"
      }
    }
  }]
}
TRUST

aws iam create-role \
  --role-name cdk-deploy-role \
  --assume-role-policy-document file://trust-policy.json

aws iam attach-role-policy \
  --role-name cdk-deploy-role \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
  # Restrict to: cloudformation:*, ecs:*, ecr:*, s3:*, iam:*, ec2:*, logs:*, es:*, ssm:*
```

---

## First-time deployment steps

```bash
# 1. Bootstrap CDK (once per account/region)
cdk bootstrap aws://<ACCOUNT_ID>/us-east-1

# 2. Set SSM parameters (see above)

# 3. Enable Bedrock models in the AWS console
#    Anthropic → Claude Sonnet  (anthropic.claude-sonnet-4-5)
#    Amazon → Titan Text Embeddings V2  (amazon.titan-embed-text-v2:0)

# 4. Push to a feature branch — pipeline runs automatically
git push origin feature/my-change

# 5. After deployment, seed OpenSearch with policy embeddings
curl -X POST http://<ALB_DNS>/admin/seed-policies

# 6. Run the sample audit to verify everything works
curl -X POST http://<ALB_DNS>/audit/sample | python3 -m json.tool

# 7. Check synthetic scenario list
curl http://<ALB_DNS>/audit/scenarios
```

---

## Local development

```bash
# Clone and configure
cp .env.example .env   # fill in AWS credentials and service endpoints

# Run Python app (real AWS credentials required for Bedrock/Textract)
cd app
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000

# Run tests
pytest tests/ -v

# CDK commands
cd cdk/expense-audit-ecr-repository-stack
yarn install && yarn cdk synth

cd ../expense-audit-app-stack
yarn install && yarn cdk synth -c env=dev -c imageTag=local
```

---

## AWS services used

| Service | Purpose |
|---|---|
| ECS Fargate | Container runtime — us-east-1 only |
| ECR | Private Docker image registry |
| AWS CDK v2 | Infrastructure as code (TypeScript) |
| AWS Textract | Document OCR |
| Amazon Bedrock (Claude) | LLM validation and report synthesis |
| Amazon Bedrock (Titan Embed v2) | 1024-dim embeddings |
| Amazon OpenSearch Service | k-NN semantic policy search |
| Amazon S3 (reports) | Audit report storage |
| Amazon S3 (docs) | Textract upload staging |
| AWS SSM Parameter Store | Secret injection into ECS tasks |
| AWS Cloud Map | Internal service discovery |
| Application Load Balancer | Public HTTPS entry point |
