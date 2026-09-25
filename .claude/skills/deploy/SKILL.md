---
name: deploy
description: "Deploy this app with Databricks Declarative Automation Bundles. Use when: validate/deploy/run by target, bind existing app, or troubleshoot deploy drift."
---

# Deploy

This repository deploys using DAB with target overlays in `targets/`.

## Standard Flow

```bash
make build-app-source TARGET=<target>
databricks bundle validate -t <target> --profile <profile>
databricks bundle deploy -t <target> --profile <profile>
```

Targets used in this repo: `dev`, `qa`, `stg`, `prd`.

## Existing App Already Exists

Bind existing app to bundle resource key `multiagent-app`:

```bash
databricks bundle deployment bind multiagent-app <app-name> --auto-approve
databricks bundle deploy -t <target> --profile <profile>
```

## Fallback When Terraform Registry Is Unavailable

```bash
databricks bundle sync -t <target> --profile <profile>
APP_SRC=$(databricks apps get <app-name> --output json --profile <profile> | jq -r '.default_source_code_path')
databricks apps deploy <app-name> --profile <profile> --source-code-path "$APP_SRC" --mode SNAPSHOT
```

## Verify Deployed App

```bash
databricks apps get <app-name> --output json --profile <profile>
databricks apps logs <app-name> --follow --profile <profile>
```

## Notes

- Always include `--profile` explicitly.
- Use the operations runbook for app-source import, app deployment, permissions, and post-deployment verification.
