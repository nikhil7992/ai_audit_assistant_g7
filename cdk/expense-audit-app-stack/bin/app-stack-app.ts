#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { ExpenseAuditAppStack } from '../lib/expense-audit-app-stack';

const app    = new cdk.App();
const appEnv = app.node.tryGetContext('env') as string ?? 'dev';

new ExpenseAuditAppStack(app, 'ExpenseAuditStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,  // resolved at deploy time via STS role
    region:  'us-east-1',
  },
  appEnv,
  description: `Expense Audit Application Stack — ${appEnv} — us-east-1`,
});
