# GitHub Pages Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the existing single-file One Class operations guide through GitHub Actions to the `github-pages` environment and expose a shareable public URL.

**Architecture:** Keep `one-class-operations-guide.html` as the source artifact. The workflow creates temporary `_site/index.html`, uploads only `_site`, and deploys it with the official GitHub Pages actions. Pages is enabled with build type `workflow`; if GitHub rejects Pages for the private repository, use the user's authorization to make it public.

**Tech Stack:** Static HTML, Node.js built-in test runner, GitHub Actions, GitHub Pages, GitHub CLI

---

### Task 1: Define the workflow contract

**Files:**
- Modify: `tests/operations-guide.test.mjs`
- Test: `tests/operations-guide.test.mjs`

- [ ] **Step 1: Write the failing test**

Add `const workflowPath = new URL('../.github/workflows/deploy-pages.yml', import.meta.url);` and test the workflow content:

```js
test('deploys only the guide through the official GitHub Pages workflow', async () => {
  const workflow = await readFile(workflowPath, 'utf8');
  assert.match(workflow, /name: Deploy GitHub Pages/);
  assert.match(workflow, /pages:\s*write/);
  assert.match(workflow, /id-token:\s*write/);
  assert.match(workflow, /name:\s*github-pages/);
  assert.match(workflow, /cp one-class-operations-guide\.html _site\/index\.html/);
  assert.match(workflow, /actions\/upload-pages-artifact@v3/);
  assert.match(workflow, /path:\s*_site/);
  assert.match(workflow, /actions\/deploy-pages@v4/);
});
```

- [ ] **Step 2: Run the test and confirm it fails because the workflow is missing**

```powershell
node --test tests/operations-guide.test.mjs
```

- [ ] **Step 3: Commit the contract test**

```powershell
git add tests/operations-guide.test.mjs
git commit -m "test: define github pages workflow contract"
```

### Task 2: Add the Pages workflow

**Files:**
- Create: `.github/workflows/deploy-pages.yml`
- Test: `tests/operations-guide.test.mjs`

- [ ] **Step 1: Create this workflow**

```yaml
name: Deploy GitHub Pages

on:
  push:
    branches: [master]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Prepare static site
        run: |
          mkdir -p _site
          cp one-class-operations-guide.html _site/index.html
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: _site
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Run all tests and whitespace checks**

```powershell
node --test tests/operations-guide.test.mjs
git diff --check
```

Expected: 11 tests pass and no whitespace errors.

- [ ] **Step 3: Commit the workflow**

```powershell
git add .github/workflows/deploy-pages.yml tests/operations-guide.test.mjs
git commit -m "ci: deploy guide to github pages"
```

### Task 3: Enable Pages and push

**Files:**
- No local file changes

- [ ] **Step 1: Try workflow-based Pages on the private repository**

```powershell
gh api --method POST repos/lipeng062013/one-class/pages -f build_type=workflow
```

Expected: Pages settings are returned. If GitHub rejects private Pages because of the account plan, continue.

- [ ] **Step 2: Apply the authorized public fallback only after that rejection**

```powershell
gh repo edit lipeng062013/one-class --visibility public --accept-visibility-change-consequences
gh api --method POST repos/lipeng062013/one-class/pages -f build_type=workflow
```

- [ ] **Step 3: Push the default branch**

```powershell
git push origin master
```

### Task 4: Verify the Deployment

**Files:**
- No local file changes

- [ ] **Step 1: Watch the newest workflow run**

```powershell
$runId = gh run list --repo lipeng062013/one-class --workflow deploy-pages.yml --limit 1 --json databaseId --jq '.[0].databaseId'
gh run watch $runId --repo lipeng062013/one-class --exit-status
```

Expected: the run concludes with `success`.

- [ ] **Step 2: Verify Pages metadata and the github-pages environment**

```powershell
gh api repos/lipeng062013/one-class/pages
gh api repos/lipeng062013/one-class/deployments --jq '.[] | select(.environment == "github-pages") | {id, environment, created_at}'
```

- [ ] **Step 3: Verify the public URL content**

```powershell
$url = gh api repos/lipeng062013/one-class/pages --jq .html_url
$response = Invoke-WebRequest -UseBasicParsing $url
$response.StatusCode
$response.Content -match '壹号教室全年运营与宣传执行方案'
```

Expected: status `200` and content check `True`.

- [ ] **Step 4: Verify final local and remote state**

```powershell
node --test tests/operations-guide.test.mjs
git status --short
git rev-parse HEAD
git rev-parse origin/master
```

Expected: 11 tests pass, worktree is clean, and local and remote commits match.
