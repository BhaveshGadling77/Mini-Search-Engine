# Contributing to Mini Search Engine


This project has three worklets, with four members in each team. During development, each team works in its own folder. Once all three worklets are complete, we will use an integration branch to bring everything together.

## Worklets

| Worklet | Responsibility | Language |
|---|---|---|
| **WL1** | Crawler & Document Model | Python |
| **WL2** | Inverted Index & Query Processing | C++ |
| **WL3** | Ranking, Caching & Evaluation | Python |

### WL1
Handles crawling, extracting and processing documents, and preparing the data needed by the index.

### WL2
Builds the index and handles query processing. The complete implementation is in **C++**.

WL2 will also provide the interface through which WL1 can provide document data and WL3 can send queries and receive results. Other worklets should use this interface rather than depending on WL2's internal implementation.

### WL3
Handles ranking, caching, CLI/REPL, and evaluation of search results.

## Repository Structure

```text
mini-search-engine/
├── wl1/
├── wl2/
├── wl3/
├── data/
├── tests/
│   ├── wl1/
│   ├── wl2/
│   └── wl3/
├── docs/
│   ├── wl1/
│   ├── wl2/
│   └── wl3/
├── README.md
└── CONTRIBUTING.md
```

Work mainly inside your assigned worklet folder. Keep its tests and documentation in the matching `tests/wlX/` and `docs/wlX/` folders.

## Branching

`main` is the stable branch.

Each worklet has an integration branch:

```text
main
├── wl1
├── wl2
└── wl3
```

Each member creates a personal branch from their worklet branch:

```text
wl1-dev-<username>
wl2-dev-<username>
wl3-dev-<username>
```

Example:

```text
wl2-dev-bhavesh
```

## Workflow

```text
Personal Branch → Worklet Branch → Integration → main
```

Create your branch, make and test your changes, then open a PR to your worklet branch.

Do not push directly to `main`.

## Integration

After WL1, WL2, and WL3 are complete, an `integration` branch will be created.

The integration phase will connect the three worklets, verify their interfaces, reorganize the temporary worklet structure if needed, and run the complete system.

```text
wl1 ──┐
wl2 ──┼──→ integration ──→ main
wl3 ──┘
```

The final integration will reach `main` through a Pull Request.

## A Few Rules

- Test your changes before opening a PR.
- Keep PRs focused and avoid unrelated changes.
- Discuss changes that affect another worklet or its interface.
- Never force-push to `main`.
- Do not commit secrets or unnecessary generated files.

**Simple rule:** Work in your worklet → test → open a PR → review → merge → integrate later.


## Starting the project

### 1. Clone the Repository.
```bash
git clone https://github.com/BhaveshGadling77/Mini-Search-Engine.git
cd Mini-Search-Engine
```

### 2. Fetch all branches
```bash
git fetch --all
```

### 3. Go to the worklet branch
For WL1:
```bash
git checkout wl1
git pull origin wl1
```
For WL2:
```bash
git checkout wl2
git pull origin wl2
```
For WL3:
```bash
git checkout wl3
git pull origin wl3
```

### 4. Create your personal development branch

for example, my username is bhavesh and from Wl2
Wl2:
```bash
git checkout -b wl2-dev-bhavesh
```
accordingly you can create your own branch w.r.t your worklet.

### 5. Push your branch to Github

```bash
git push -u origin wl2-dev-bhavesh
```

Replace the branch name according to your worklet.
After that, your normal workflow is simply:

```bash
git add .
git commit -m "Describe your changes"
git push
```

Then create a PR if you want to:
```bash
wl2-dev-bhavesh -> wl2
```
according to **your branch**.


Also if possible maintain the commit message convention:
Commit should be like this:
```text
fix: Describe in short
chore: Describe in short
feat: Describe in short
rem: Describe what removed
docs: describe
so on ...
```
