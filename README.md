# AutoPartsNg Documentation

Welcome to the AutoPartsNg platform! This repository leverages an AWS SAM (Serverless Application Model) microservice architecture. 

## Table of Contents
1. [Adding New Services](#adding-new-services)
2. [Git Workflow & Branching Strategy](#git-workflow--branching-strategy)
3. [Deployment Commands](#deployment-commands)

---

## Adding New Services

This architecture relies on decoupled, individually configured services orchestrated by a root SAM `template.yml`.

### Step-by-Step Guide
1. **Create the Service Directory**: 
   Microservices live directly under the `Microservices/` directory. 
   ```bash
   mkdir -p Microservices/MyNewService/src
   ```

2. **Define the Local Template**:
   Inside your new service directory, create a local `template.yml` containing the specific AWS resources (Lambdas, Roles, S3 Buckets, DynamoDB tables) the service needs to operate autonomously. Ensure your template contains an `Outputs:` section for exporting necessary ARNs (such as API Gateway IDs or Lambda ARNs) that other microservices might need to consume.

3. **Orchestrate in the Root `template.yml`**:
   Link your new service into the root `/template.yml` under the `Resources` block using the `AWS::Serverless::Application` type, passing down matching global variables required in parameters.
   ```yaml
     MyNewServiceComponent:
       Type: AWS::Serverless::Application
       Properties:
         Location: Microservices/MyNewService/template.yml
         Parameters:
           Stage: !Ref Stage
           LambdaPowerToolsLayerKey: !Ref LambdaPowerToolsLayerKey
   ```

4. **Verify Dependencies in `samconfig.toml`**:
   If the new service introduces parameters that require custom overrides per environment (Dev or Prod), map explicitly within `/samconfig.toml`. 

---

## Git Workflow & Branching Strategy

Our source code strictly adheres to a feature-branch workflow. 

### 1. Synchronize the Base Branch
Always base your new features off the most up-to-date core branch (usually `main` or `master`).
```bash
git checkout main
git pull origin main
```

### 2. Create a Feature Branch
Branches should be properly named using the `feature/`, `bugfix/`, or `hotfix/` prefixes depending on the task context.
```bash
git checkout -b feature/your-feature-name
```
*Example: `feature/payment-integration` or `bugfix/contact-query-issue`*

### 3. Record Changes (Committing)
Write clear, concise commit messages. Best practice encourages atomic commits representing logical units of work.
```bash
git add .
git commit -m "feat(module): standard descriptive message regarding the commit"
```
*Note: Large build artifacts (like `.aws-sam/` or `.zip` files) are explicitly defined within `.gitignore` and should never be pushed to your branch.*

### 4. Push Your Work
If this is the first push for the branch, bind it to your origin upstream server:
```bash
git push --set-upstream origin feature/your-feature-name
```
For subsequent pushes on this branch:
```bash
git push
```

### 5. Finalizing Work
On GitHub (or your Git provider of choice), navigate to your newly pushed branch and select **"Open Pull Request."** Upon PR approval and merge, you can safely delete the local feature branch to maintain workstation hygiene.
```bash
git branch -d feature/your-feature-name
```

---

## Deployment Commands

We utilize automated deployments bound via parameters found in `samconfig.toml`.

To build the service natively (leveraging caches for speed enhancements):
```bash
sam build --cached
```

To directly deploy targeted environment stacks (Dev or Prod), instruct SAM to reference defined environments:
```bash
sam deploy --config-env dev --profile autopartsng
# or
sam deploy --config-env prod --profile autopartsng
```
*(Ensure valid AWS keys are configured prior to running deploy scripts by utilizing `aws configure --profile autopartsng`)*
