# Resource Library

The **Resources** root in the sidebar indexes your resources folder: a
searchable tree with previews, and tags and notes kept in a sidecar file so
the resources themselves are never written.

![Resources with a Python file previewed](../library-python-dark.png)

- Search covers file names and the text of `.py`, `.txt`, `.md`, `.csv` and
  `.pdf` files. Office files (`.doc`, `.docx`, `.ppt`, `.pptx`, `.pub`,
  `.xlsx`) are **never parsed**; they open in their native app.
- Previews: Python with highlighting, plain text, images, the first page of
  a PDF, or an open-externally card.
- Cloud placeholders (files not downloaded on this Mac) are marked, not fatal.
- Re-index is incremental; the first index of a few hundred files takes seconds.

Tools reach the library through a picker: ⌘O, or *From library…* on any
file input.

```bash
staff library index
staff library search while --kind python
staff library tags "Python/loops.py" --set loops,ks3 --notes "Good starter"
```
