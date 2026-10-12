# Reporting a privacy or security problem

Staffroom is built never to hold pupil data. If you find that it does, or
could, please tell the maintainer **privately**, not in a public issue. For
example:

- a name, candidate number or other identifier got past the identifier filter
  and into an output, a preview, the log or the Library index;
- a file from the resources folder was changed, or something was written
  where it should not be;
- pupil code ran outside the sandboxed runner;
- anything that could send data off the Mac.

## How to report

Use GitHub's private reporting:
[Report a vulnerability](https://github.com/ColePoppleton/Staffroom/security/advisories/new)
(the **Security** tab, then **Report a vulnerability**). Only the maintainer
sees what you write there.

If that page says private reporting is not available, open a
[Bug report](https://github.com/ColePoppleton/Staffroom/issues/new/choose)
titled *Privacy problem: please get in touch*, write nothing else about it,
and the maintainer will arrange a private route.

Whichever route you use, do not include real pupil data. Describe what
happened, and if an example is needed, use an invented one (the
[example files](https://github.com/ColePoppleton/Staffroom/tree/main/examples)
are a good start).

## What happens next

The maintainer replies on the report, fixes the problem, releases the fix,
and records it in the changelog without repeating anything sensitive.

The [Privacy page](https://colepoppleton.github.io/Staffroom/guide/privacy/)
explains what Staffroom stores and where.
