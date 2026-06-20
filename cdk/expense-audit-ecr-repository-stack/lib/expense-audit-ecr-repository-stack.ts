import * as cdk from 'aws-cdk-lib';
import * as ecr  from 'aws-cdk-lib/aws-ecr';
import { Construct } from 'constructs';

export interface ExpenseAuditEcrRepositoryStackProps extends cdk.StackProps {
  /** Deployment environment: dev | staging | prod */
  appEnv: string;
}

/**
 * ExpenseAuditEcrRepositoryStack
 *
 * Creates one ECR repository per microservice.
 * Deployed independently of the application stack so images can be pushed
 * before the full ECS infrastructure exists.
 */
export class ExpenseAuditEcrRepositoryStack extends cdk.Stack {
  /** Map of service name → repository (exported for use by the app stack) */
  public readonly repositories: Record<string, ecr.Repository>;

  constructor(scope: Construct, id: string, props: ExpenseAuditEcrRepositoryStackProps) {
    super(scope, id, props);

    const { appEnv } = props;

    const serviceNames = [
      'expense-audit-gateway',
      'expense-audit-ocr',
      'expense-audit-validation',
      'expense-audit-duplicate',
      'expense-audit-audit',
      'expense-audit-frontend'
    ];

    this.repositories = {};

    for (const name of serviceNames) {
      const repo = new ecr.Repository(this, `${name}-repo`, {
        repositoryName:     `${name}-${appEnv}`,
        removalPolicy:      cdk.RemovalPolicy.RETAIN,   // never auto-delete images
        imageScanOnPush:    true,
        imageTagMutability: ecr.TagMutability.MUTABLE,
        lifecycleRules: [
          {
            description:   'Retain last 10 tagged images',
            maxImageCount: 10,
            tagStatus:     ecr.TagStatus.ANY,
          },
        ],
      });

      // Export repository URI so other stacks and GitHub Actions can reference it
      new cdk.CfnOutput(this, `${name}-uri`, {
        value:      repo.repositoryUri,
        exportName: `ExpenseAudit-${appEnv}-${name}-Uri`,
        description: `ECR URI for ${name} in ${appEnv}`,
      });

      this.repositories[name] = repo;
    }

    // Stack-level tags
    cdk.Tags.of(this).add('Project',     'expense-audit');
    cdk.Tags.of(this).add('Environment', appEnv);
    cdk.Tags.of(this).add('ManagedBy',   'cdk');
  }
}