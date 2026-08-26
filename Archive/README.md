# Optional recipe archive

The curated Bloody Dave library does not depend on this folder.

To add the offline archive later, place the generated archive files here:

```text
Archive/
├── index.json
├── recipes/
└── images/          # optional
```

Reload the app. No application rebuild is required.

Archive recipes remain separate from the curated library until promoted. In this static build, promotion is prepared locally and exported as JSON for addition to the source `recipes.json`.
