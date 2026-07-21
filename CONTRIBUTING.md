# Contributing to AuraGram

Thanks for your interest in contributing! Please follow these guidelines to keep collaboration smooth.

---

## 🗂️ Git Workflow

```
main          ← stable, production-ready code only
  └── develop ← main integration branch
        ├── feat/feature-name
        ├── fix/bug-name
        └── ai/model-or-pipeline-name
```

**Rules:**
- **Never commit directly to `main` or `develop`**
- All changes go through a Pull Request
- PRs require at least **1 approval** before merging
- Your branch must be up to date with `develop` before merging

---

## 🌿 Branch Naming

```
feat/user-authentication
fix/image-upload-timeout
ai/llava-caption-service
refactor/post-feed-pagination
docs/api-endpoints
```

---

## ✍️ Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description in lowercase>

[body — optional, explain WHY if needed]

[footer — optional, e.g. Closes #42]
```

**Examples:**
```
feat(auth): add JWT refresh token rotation
fix(upload): handle Cloudinary timeout error
ai(caption): integrate LLaVA GGUF local inference
docs(api): update post endpoints documentation
```

**Valid types:**

| Type | When to use |
|---|---|
| `feat` | Add a new feature |
| `fix` | Fix a bug |
| `docs` | Documentation changes |
| `style` | Code formatting (no logic changes) |
| `refactor` | Refactor without adding features or fixing bugs |
| `test` | Add or update tests |
| `chore` | Update dependencies, config |
| `perf` | Performance improvements |
| `ai` | Add or modify AI models or pipelines |

---

## 📬 Pull Request

When opening a PR, fill in the following template:

```markdown
## Description
<!-- Summarize what this PR changes -->

## Related Issue
Closes #<issue number>

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Added / updated unit tests
- [ ] All tests pass (`pytest tests/ -v`)
- [ ] Manually tested on local environment

## Screenshots (if UI changes)
```

---

## 🧪 Code Standards

### Python (Backend)
- Formatter: **Black** (`black .`)
- Linter: **Ruff** (`ruff check .`)
- Type hints required for all functions
- Docstrings for all public functions and classes

```bash
# Run before committing
black backend/
ruff check backend/
pytest tests/ -v
```

### JavaScript (Frontend)
- Formatter: **Prettier**
- Linter: **ESLint**
- Components must have PropTypes or TypeScript types

```bash
npm run lint
npm run format
npm run test
```

---

## 🚫 What NOT to Do

- Commit `.env` files, API keys, or passwords
- Push AI model files (`.gguf`, `.safetensors`, `.pt`) to the repo — use `ai_models/download_models.py` instead
- Merge your own PR before it has been reviewed
- Leave `console.log` debug statements in production code
- Use `Any` type in Python when it can be avoided

---

## 📁 File Structure for New Features

When adding a new feature, follow this structure:

**Backend (FastAPI):**
```
backend/api/v1/     ← thin route handlers (call services only)
backend/services/   ← business logic
backend/models/     ← Pydantic schemas
tests/              ← corresponding tests
```

**Frontend (React):**
```
frontend/src/
  components/       ← reusable UI components
  pages/            ← page-level components
  hooks/            ← custom hooks
  services/         ← API calls
  store/            ← state management
```

---

## 🐛 Reporting Bugs

Open a [new Issue](../../issues/new) and include:
- A clear **description** of the bug
- **Steps to reproduce**
- **Expected** vs **actual** behavior
- **Environment**: OS, Python/Node version, GPU
- **Error logs** (if any)

---

## 💡 Suggesting Features

Open an Issue with the `enhancement` label and describe:
- What the feature is
- Why it's needed (use case)
- Proposed implementation (if you have one)
