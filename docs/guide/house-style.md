# House style

Every worksheet, key, trace table, bug sheet and do-now is rendered through
one document model to docx (python-docx), PDF (reportlab) and plain text, so
they all look the same:

- header: your header text, the title, the topic and the date;
- footer: your footer text and the page number;
- monospace blocks for code; numbered questions with ruled answer space;
- an answer key split into a separate `_key` file.

Set the header and footer text in **Settings › Worksheets**. Tools that
produce sheets accept `--format docx|pdf|both`.
