# House style

Every sheet and key (Worksheet, Parsons, Trace, Bugs, Fade and Quiz's
do-now) is rendered through
one document model to docx (python-docx), PDF (reportlab) and plain text, so
they all look the same:

- header: your header text, the title, the topic and the date;
- footer: your footer text and the page number;
- monospace blocks for code; numbered questions with ruled answer space;
- numbered cut-out boxes with dashed cut lines (Parsons blocks) and answer
  grids, laid out to use the page;
- an answer key split into a separate `_key` file.

Set the header and footer text in **Settings › Worksheets**. Worksheet,
Parsons, Trace, Bugs and Fade accept `--format docx|pdf|both` (*Output* in
the panel); Quiz's do-now always writes both.
