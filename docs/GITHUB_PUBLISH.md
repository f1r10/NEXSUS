# Publishing this local project

The connected GitHub integration returned **403 Resource not accessible by integration** when attempting to write the initial file to `f1r10-cmd/nexus`. The repository is empty, and the connector's effective GitHub App permission must be changed by its owner or a separately authorized Git client must be used. A metadata `push=true` flag did not permit the write operation.

For an authorized maintainer, after reviewing the code and enabling GitHub write access:

```bash
# Extract the NEXUS package into a directory (not into another Git repository)
cd nexus
cp .env.example .env
# Edit .env locally. Never commit .env.
git init -b main
git add .
git commit -m "feat: initialize NEXUS investigation workspace v0.1"
git remote add origin https://github.com/f1r10-cmd/nexus.git
git push -u origin main
```

If the remote main branch has acquired commits before publication, **do not force push**. Fetch and reconcile those commits first, then push a feature branch or create a pull request.
