# Editing & publishing the DocuMind Wiki

The public Wiki at https://github.com/dyh1265/RAG/wiki is **a mirror** of this folder. We edit Markdown here, version it with the rest of the code, and a GitHub Action pushes it to the Wiki on every push to `master`.

That gets us three things vanilla wikis don't:

- Pull-request review on wiki changes.
- Atomic commits that change wiki + code together (e.g. add a feature flag here *and* document it).
- Reproducible wiki state — anyone can rebuild the wiki from any commit.

## Layout

| File | Becomes |
|---|---|
| `Home.md` | https://github.com/dyh1265/RAG/wiki/Home |
| `Architecture.md` | https://github.com/dyh1265/RAG/wiki/Architecture |
| `RAG-Pipeline.md` | https://github.com/dyh1265/RAG/wiki/RAG-Pipeline |
| `Retrieval.md` | https://github.com/dyh1265/RAG/wiki/Retrieval |
| `Evaluation.md` | https://github.com/dyh1265/RAG/wiki/Evaluation |
| `Configuration.md` | https://github.com/dyh1265/RAG/wiki/Configuration |
| `_Sidebar.md` | The sidebar GitHub renders on every wiki page |
| `_Footer.md` | The footer GitHub renders on every wiki page |

Filenames map directly: GitHub Wiki uses the filename (without `.md`) as the URL slug, and *hyphens are kept literally* — so `RAG-Pipeline.md` is reachable at `/wiki/RAG-Pipeline` and inter-page links should use that exact slug: `[Retrieval](Retrieval)`.

## Internal links

Within wiki pages, link by slug (no path, no `.md`):

```markdown
See [Retrieval](Retrieval) for the fusion details.
```

GitHub renders that correctly on the published wiki. The same link also works when viewing these files locally with most Markdown renderers, just without resolving to the wiki host.

For links to *code* in the repo, use full GitHub URLs anchored to `master` (or a tag) so the wiki keeps working after files move:

```markdown
See [`backend/core/pipeline.py`](https://github.com/dyh1265/RAG/blob/master/backend/core/pipeline.py).
```

## One-time setup (already done; here for reference)

1. **Initialise the wiki repo.** Wikis only exist after the first page is created via the GitHub UI. Go to https://github.com/dyh1265/RAG/wiki and click *Create the first page* — anything will do; the workflow will overwrite it.
2. **Allow Actions to push to the wiki.** Repo → Settings → Actions → General → *Workflow permissions* → set to *Read and write permissions*. The Wiki repo (`dyh1265/RAG.wiki.git`) accepts the default `GITHUB_TOKEN` once this is on.
3. *(Optional)* If for any reason `GITHUB_TOKEN` is not enough — most commonly because the wiki sits in a different account — create a fine-grained PAT with `Contents: read/write` on this repo, save it as a repo secret named `WIKI_TOKEN`, and the workflow will prefer that automatically.

## Day-to-day workflow

```bash
# edit
$EDITOR docs/wiki/Retrieval.md

# preview locally (any Markdown previewer works)
glow docs/wiki/Retrieval.md

# commit, push, done
git add docs/wiki/Retrieval.md
git commit -m "docs(wiki): clarify RRF fusion constant"
git push origin master
```

Within ~30 seconds, the [Wiki Sync workflow](https://github.com/dyh1265/RAG/actions/workflows/wiki.yml) republishes the page.

## Manual fallback

If the workflow is disabled for any reason, you can sync by hand:

```bash
git clone https://github.com/dyh1265/RAG.wiki.git
cp docs/wiki/*.md RAG.wiki/
( cd RAG.wiki && git add -A && git commit -m "Sync wiki" && git push )
```
