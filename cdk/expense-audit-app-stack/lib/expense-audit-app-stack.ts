import * as cdk  from 'aws-cdk-lib';
import * as ec2  from 'aws-cdk-lib/aws-ec2';
import * as ecs  from 'aws-cdk-lib/aws-ecs';
import * as ecr  from 'aws-cdk-lib/aws-ecr';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as iam  from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3   from 'aws-cdk-lib/aws-s3';
import * as ssm  from 'aws-cdk-lib/aws-ssm';
import * as sd   from 'aws-cdk-lib/aws-servicediscovery';
import { Construct } from 'constructs';

export interface ExpenseAuditAppStackProps extends cdk.StackProps {
  /** Deployment environment: dev | staging | prod */
  appEnv: string;
}

/**
 * ExpenseAuditAppStack
 *
 * Provisions all ECS Fargate resources for the Expense Audit platform:
 *   - VPC with public + private subnets
 *   - ECS Fargate cluster with Cloud Map service discovery
 *   - Task definitions for all five services
 *   - Application Load Balancer (gateway only)
 *   - S3 buckets (reports, documents)
 *   - IAM task role with least-privilege policies
 *   - CloudWatch log groups
 *
 * PREREQUISITES:
 *   - ECR repositories must already exist (deploy expense-audit-ecr-repository-stack first)
 *   - OpenSearch domain endpoint must be available (set in SSM at deploy time)
 *   - Image tag is passed via CDK context: --context imageTag=<sha>
 */
export class ExpenseAuditAppStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ExpenseAuditAppStackProps) {
    super(scope, id, props);

    const { appEnv } = props;

    // ── Context / config ────────────────────────────────────────────────────
    // PLACEHOLDER: imageTag is set by GitHub Actions via --context imageTag=$GITHUB_SHA
    const imageTag          = this.node.tryGetContext('imageTag')          as string ?? 'latest';
    const bedrockRegion     = this.node.tryGetContext('bedrockRegion')     as string ?? 'us-east-1';
    const bedrockLlmModel   = this.node.tryGetContext('bedrockLlmModel')   as string ?? 'anthropic.claude-sonnet-4-5';
    const bedrockEmbedModel = this.node.tryGetContext('bedrockEmbedModel') as string ?? 'amazon.titan-embed-text-v2:0';

    // PLACEHOLDER: SSM parameters — set these before deploying
    const opensearchEndpoint = ssm.StringParameter.valueForStringParameter(this, `/${appEnv}/expense-audit/opensearch-endpoint`);
    const opensearchPassword = ssm.StringParameter.valueForStringParameter(this, `/${appEnv}/expense-audit/opensearch-password`);

    // ── VPC ─────────────────────────────────────────────────────────────────
    const vpc = new ec2.Vpc(this, 'Vpc', {
      maxAzs:          2,
      natGateways:     1,
      subnetConfiguration: [
        { name: 'Public',  subnetType: ec2.SubnetType.PUBLIC,           cidrMask: 24 },
        { name: 'Private', subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS, cidrMask: 24 },
      ],
    });

    // ── S3 buckets ───────────────────────────────────────────────────────────
    const reportsBucket = new s3.Bucket(this, 'ReportsBucket', {
      bucketName:          `expense-audit-reports-${appEnv}-${this.account}`,
      versioned:           true,
      encryption:          s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess:   s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy:       cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [{
        id:              'TransitionToIA',
        transitions:     [{ storageClass: s3.StorageClass.INFREQUENT_ACCESS, transitionAfter: cdk.Duration.days(90) }],
        enabled:         true,
      }],
    });

    const docsBucket = new s3.Bucket(this, 'DocsBucket', {
      bucketName:        `expense-audit-docs-${appEnv}-${this.account}`,
      versioned:         false,
      encryption:        s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy:     cdk.RemovalPolicy.DESTROY,
      lifecycleRules: [{
        id:         'DeleteUploadsAfter7Days',
        prefix:     'uploads/',
        expiration: cdk.Duration.days(7),
        enabled:    true,
      }],
    });

    // ── IAM task role ─────────────────────────────────────────────────────────
    const taskRole = new iam.Role(this, 'EcsTaskRole', {
      roleName:        `expense-audit-task-role-${appEnv}`,
      assumedBy:       new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      description:     'Least-privilege role for Expense Audit ECS tasks',
    });

    reportsBucket.grantReadWrite(taskRole);
    docsBucket.grantReadWrite(taskRole);

    taskRole.addToPolicy(new iam.PolicyStatement({
      sid:       'TextractAccess',
      effect:    iam.Effect.ALLOW,
      actions:   ['textract:AnalyzeDocument', 'textract:DetectDocumentText', 'textract:StartDocumentAnalysis', 'textract:GetDocumentAnalysis'],
      resources: ['*'],   // Textract does not support resource-level restrictions
    }));

    taskRole.addToPolicy(new iam.PolicyStatement({
      sid:     'BedrockAccess',
      effect:  iam.Effect.ALLOW,
      actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
      resources: [
        `arn:aws:bedrock:${bedrockRegion}::foundation-model/anthropic.claude-*`,
        `arn:aws:bedrock:${bedrockRegion}::foundation-model/amazon.titan-embed-*`,
      ],
    }));

    taskRole.addToPolicy(new iam.PolicyStatement({
      sid:       'OpenSearchAccess',
      effect:    iam.Effect.ALLOW,
      actions:   ['es:ESHttpGet', 'es:ESHttpPost', 'es:ESHttpPut', 'es:ESHttpDelete'],
      resources: [`arn:aws:es:${this.region}:${this.account}:domain/expense-audit-${appEnv}/*`],
    }));

    taskRole.addToPolicy(new iam.PolicyStatement({
      sid:       'SsmAccess',
      effect:    iam.Effect.ALLOW,
      actions:   ['ssm:GetParameter', 'ssm:GetParameters'],
      resources: [`arn:aws:ssm:${this.region}:${this.account}:parameter/${appEnv}/expense-audit/*`],
    }));

    taskRole.addToPolicy(new iam.PolicyStatement({
      sid:       'CloudWatchLogs',
      effect:    iam.Effect.ALLOW,
      actions:   ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
      resources: ['*'],
    }));

    const executionRole = new iam.Role(this, 'EcsExecutionRole', {
      roleName:  `expense-audit-execution-role-${appEnv}`,
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonECSTaskExecutionRolePolicy')],
    });

    // ── ECS Cluster + Cloud Map ───────────────────────────────────────────────
    const cluster = new ecs.Cluster(this, 'ExpenseAuditCluster', {
      clusterName:        `ExpenseAuditCluster-${appEnv}`,
      vpc,
      containerInsights:  true,
    });

    const namespace = new sd.PrivateDnsNamespace(this, 'ServiceNamespace', {
      name: `expense-audit-${appEnv}.local`,
      vpc,
    });

    // ── Security groups ───────────────────────────────────────────────────────
    const albSg = new ec2.SecurityGroup(this, 'AlbSg', {
      vpc,
      description: 'ALB inbound',
      allowAllOutbound: true,
    });
    albSg.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(80),  'HTTP');
    albSg.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(443), 'HTTPS');

    const serviceSg = new ec2.SecurityGroup(this, 'ServiceSg', {
      vpc,
      description: 'ECS task communication',
      allowAllOutbound: true,
    });
    serviceSg.addIngressRule(albSg,     ec2.Port.tcpRange(8000, 8004), 'From ALB');
    serviceSg.addIngressRule(serviceSg, ec2.Port.tcpRange(8000, 8004), 'Service mesh');

    // ── ALB ───────────────────────────────────────────────────────────────────
    const alb = new elbv2.ApplicationLoadBalancer(this, 'Alb', {
      loadBalancerName: `expense-audit-alb-${appEnv}`,
      vpc,
      internetFacing:   true,
      securityGroup:    albSg,
      vpcSubnets:       { subnetType: ec2.SubnetType.PUBLIC },
    });

    const listener = alb.addListener('HttpListener', {
      port: 80,
      defaultAction: elbv2.ListenerAction.fixedResponse(503, { messageBody: 'Service unavailable' }),
    });

    // ── Helper: build a Fargate service ──────────────────────────────────────
    const buildService = (
      name:        string,
      port:        number,
      cpu:         number,
      memory:      number,
      environment: Record<string, string>,
      isPublic:    boolean,
    ): ecs.FargateService => {
      const logGroup = new logs.LogGroup(this, `${name}-logs`, {
        logGroupName:  `/ecs/expense-audit-${appEnv}/${name}`,
        retention:     logs.RetentionDays.ONE_MONTH,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      });

      // ECR repo reference — created by the ECR stack
      const repo = ecr.Repository.fromRepositoryName(this, `${name}-repo`, `expense-audit-${name}-${appEnv}`);

      const taskDef = new ecs.FargateTaskDefinition(this, `${name}-task`, {
        family:         `expense-audit-${appEnv}-${name}`,
        cpu,
        memoryLimitMiB: memory,
        taskRole,
        executionRole,
      });

      taskDef.addContainer(`${name}-container`, {
        image:          ecs.ContainerImage.fromEcrRepository(repo, imageTag),
        portMappings:   [{ containerPort: port, protocol: ecs.Protocol.TCP }],
        environment,
        logging:        ecs.LogDrivers.awsLogs({ streamPrefix: 'ecs', logGroup }),
        healthCheck: {
          command:     ['CMD-SHELL', `python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:${port}/health')" || exit 1`],
          interval:    cdk.Duration.seconds(30),
          timeout:     cdk.Duration.seconds(10),
          retries:     3,
          startPeriod: cdk.Duration.seconds(30),
        },
      });

      const service = new ecs.FargateService(this, `${name}-service`, {
        serviceName:       `expense-audit-${appEnv}-${name}`,
        cluster,
        taskDefinition:    taskDef,
        desiredCount:      2,
        securityGroups:    [serviceSg],
        vpcSubnets:        { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
        assignPublicIp:    false,
        cloudMapOptions: {
          name:           `${name}-service`,
          cloudMapNamespace: namespace,
          dnsRecordType:  sd.DnsRecordType.A,
          dnsTtl:         cdk.Duration.seconds(10),
        },
      });

      if (isPublic) {
        const tg = new elbv2.ApplicationTargetGroup(this, `${name}-tg`, {
          targetGroupName: `expense-audit-${appEnv}-${name}`,
          vpc,
          protocol:        elbv2.ApplicationProtocol.HTTP,
          port,
          targetType:      elbv2.TargetType.IP,
          healthCheck: {
            path:                   '/health',
            interval:               cdk.Duration.seconds(30),
            healthyThresholdCount:  2,
            unhealthyThresholdCount: 3,
          },
        });
        service.attachToApplicationTargetGroup(tg);
        // Fix: conditions are required when priority is set
        listener.addTargetGroups(`${name}-rule`, {
          targetGroups: [tg],
          priority:     10,
          conditions:   [elbv2.ListenerCondition.pathPatterns(['/api/*', '/health', '/docs', '/redoc'])],
        });
      }

      return service;
    };

    // ── Common environment variables ──────────────────────────────────────────
    const commonEnv = {
      APP_ENV:              appEnv,
      AWS_DEFAULT_REGION:   this.region,
      BEDROCK_REGION:       bedrockRegion,
      BEDROCK_LLM_MODEL:    bedrockLlmModel,
      BEDROCK_EMBED_MODEL:  bedrockEmbedModel,
      OPENSEARCH_ENDPOINT:  opensearchEndpoint,
      OPENSEARCH_INDEX:     'expense-policies',
      OPENSEARCH_USERNAME:  'admin',
      OPENSEARCH_PASSWORD:  opensearchPassword,
      REPORTS_S3_BUCKET:    reportsBucket.bucketName,
      TEXTRACT_S3_BUCKET:   docsBucket.bucketName,
    };

    // ── Deploy backend services ───────────────────────────────────────────────
    buildService('gateway',    8000, 512,  1024, { ...commonEnv, PORT: '8000' }, true);
    buildService('ocr',        8001, 1024, 2048, { ...commonEnv, PORT: '8001' }, false);
    buildService('validation', 8002, 1024, 2048, { ...commonEnv, PORT: '8002' }, false);
    buildService('duplicate',  8003, 1024, 2048, { ...commonEnv, PORT: '8003' }, false);
    buildService('audit',      8004, 1024, 2048, { ...commonEnv, PORT: '8004' }, false);

    // ── Frontend service (React + nginx on port 80) ───────────────────────────
    const frontendLogGroup = new logs.LogGroup(this, 'frontend-logs', {
      logGroupName:  `/ecs/expense-audit-${appEnv}/frontend`,
      retention:     logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const frontendRepo = ecr.Repository.fromRepositoryName(
      this, 'frontend-repo',
      `expense-audit-frontend-${appEnv}`
    );

    const frontendTaskDef = new ecs.FargateTaskDefinition(this, 'frontend-task', {
      family:         `expense-audit-${appEnv}-frontend`,
      cpu:            256,
      memoryLimitMiB: 512,
      taskRole,
      executionRole,
    });

    frontendTaskDef.addContainer('frontend-container', {
      image:        ecs.ContainerImage.fromEcrRepository(frontendRepo, imageTag),
      portMappings: [{ containerPort: 80, protocol: ecs.Protocol.TCP }],
      environment:  { APP_ENV: appEnv },
      logging:      ecs.LogDrivers.awsLogs({ streamPrefix: 'ecs', logGroup: frontendLogGroup }),
      healthCheck: {
        command:     ['CMD-SHELL', 'wget -qO- http://localhost/ || exit 1'],
        interval:    cdk.Duration.seconds(30),
        timeout:     cdk.Duration.seconds(5),
        retries:     3,
        startPeriod: cdk.Duration.seconds(15),
      },
    });

    const frontendService = new ecs.FargateService(this, 'frontend-service', {
      serviceName:    `expense-audit-${appEnv}-frontend`,
      cluster,
      taskDefinition: frontendTaskDef,
      desiredCount:   1,
      securityGroups: [serviceSg],
      vpcSubnets:     { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      assignPublicIp: false,
      cloudMapOptions: {
        name:              'frontend-service',
        cloudMapNamespace: namespace,
        dnsRecordType:     sd.DnsRecordType.A,
        dnsTtl:            cdk.Duration.seconds(10),
      },
    });

    // Frontend target group — catches all traffic not matched by the API rule (priority 20 > 10)
    const frontendTg = new elbv2.ApplicationTargetGroup(this, 'frontend-tg', {
      targetGroupName: `expense-audit-${appEnv}-frontend`,
      vpc,
      protocol:        elbv2.ApplicationProtocol.HTTP,
      port:            80,
      targetType:      elbv2.TargetType.IP,
      healthCheck: {
        path:                   '/',
        interval:               cdk.Duration.seconds(30),
        healthyThresholdCount:  2,
        unhealthyThresholdCount: 3,
      },
    });
    frontendService.attachToApplicationTargetGroup(frontendTg);
    // Lower priority number = higher precedence; frontend catches remaining traffic (priority 20)
    listener.addTargetGroups('frontend-rule', {
      targetGroups: [frontendTg],
      priority:     20,
      conditions:   [elbv2.ListenerCondition.pathPatterns(['/*'])],
    });

    // ── Outputs ───────────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, 'AlbDnsName', {
      value:       alb.loadBalancerDnsName,
      exportName:  `ExpenseAudit-${appEnv}-AlbDns`,
      description: 'Application Load Balancer DNS name',
    });

    new cdk.CfnOutput(this, 'ReportsBucketName', {
      value:       reportsBucket.bucketName,
      exportName:  `ExpenseAudit-${appEnv}-ReportsBucket`,
    });

    new cdk.CfnOutput(this, 'DocsBucketName', {
      value:       docsBucket.bucketName,
      exportName:  `ExpenseAudit-${appEnv}-DocsBucket`,
    });

    new cdk.CfnOutput(this, 'ClusterName', {
      value:       cluster.clusterName,
      exportName:  `ExpenseAudit-${appEnv}-ClusterName`,
    });

    // Stack tags
    cdk.Tags.of(this).add('Project',     'expense-audit');
    cdk.Tags.of(this).add('Environment', appEnv);
    cdk.Tags.of(this).add('ManagedBy',   'cdk');
  }
}