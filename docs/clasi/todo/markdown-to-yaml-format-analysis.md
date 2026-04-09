---
status: pending
---

# Markdown-to-YAML Format Analysis

## Context

You asked: how well could our current markdown content format translate to YAML,
especially from an editing/authoring experience perspective?

## What the Current Format Actually Is

Each `.md` file holds **multiple records** separated by `# H1` headings. A
record has up to four "zones":

1. **H1 title** — becomes `title`
2. **First paragraph** — becomes `blurb`
3. **Second paragraph** — becomes `description`
4. **Custom HTML tags** — `<content>...</content>`, `<enroll>...</enroll>`, etc.
5. **Fenced YAML code block** — all structured metadata (slug, topics, dates, etc.)

So ironically, the structured data is *already YAML* — it's just embedded
inside a fenced code block within markdown.

### Example: a weekly class record today

```markdown
# Introduction to Python

Beginning students' first experience with Python programming.

This foundational course introduces students in grades 4-12 to the
Python programming language for the first time.

<content> This foundational course introduces students in grades 4-12 to the
Python programming language for the first time. Students learn basic
programming concepts through engaging, hands-on projects... </content>

<enroll>$title is included in our Weekly Classes, so to take this class
enroll in weekly classes and tell your instructor you want to study
$title.</enroll>

\```
slug: intro-python
image: python.png
level: beginner
topics: python, programming
categories: python
services: 270616, 255811
enrollments: enroll-group-classes
programs: python-programming
curriculum: https://league-curriculum.github.io/Python-Introduction/
cta: register-interest-league-labs-cta
location_code: CV
see_also: intro-python-meetup
\```
```

### Example: a person record today

```markdown
# Eric Busboom

Executive Director and Board Chair.

\```
slug: eric-busboom-staff
title: Eric Busboom
name: Eric Busboom
role: Executive Director · Board Chair
email: eric.busboom@jointheleague.org
image: images/staff/EricBusboom.png
categories:
  - staff
  - board
rank: 1
\```
```

---

## What It Would Look Like as YAML

### Option A: One YAML file per collection (mirrors current multi-record .md files)

```yaml
# classes/weekly.yaml
- slug: intro-python
  title: Introduction to Python
  blurb: Beginning students' first experience with Python programming.
  description: >
    This foundational course introduces students in grades 4-12 to the
    Python programming language for the first time.
  content: >
    This foundational course introduces students in grades 4-12 to the
    Python programming language for the first time. Students learn basic
    programming concepts through engaging, hands-on projects...
  enroll: >
    $title is included in our Weekly Classes, so to take this class
    enroll in weekly classes and tell your instructor you want to study
    $title.
  image: python.png
  level: beginner
  topics: [python, programming]
  categories: [python]
  services: [270616, 255811]
  enrollments: enroll-group-classes
  programs: [python-programming]
  curriculum: https://league-curriculum.github.io/Python-Introduction/
  cta: [register-interest-league-labs-cta]
  location_code: CV
  see_also: intro-python-meetup

- slug: python-apprentice
  title: Python Apprentice
  ...
```

### Option B: One YAML file per record

```yaml
# classes/intro-python.yaml
slug: intro-python
title: Introduction to Python
blurb: Beginning students' first experience with Python programming.
description: >
  This foundational course introduces students in grades 4-12...
content: >
  This foundational course introduces students in grades 4-12...
image: python.png
level: beginner
topics: [python, programming]
...
```

### People would look like:

```yaml
# people.yaml
- slug: eric-busboom-staff
  title: Eric Busboom
  name: Eric Busboom
  role: "Executive Director · Board Chair"
  email: eric.busboom@jointheleague.org
  image: images/staff/EricBusboom.png
  categories: [staff, board]
  rank: 1
```

---

## Assessment: How Well Does It Convert?

### What gets BETTER in YAML

1. **No more dual-format confusion.** Today each record is a hybrid: some data
   lives in positional markdown (first para = blurb, second = description),
   some in custom HTML tags, some in a YAML code block. In pure YAML it's all
   one format — every field is an explicit key.

2. **No positional fragility.** The current parser relies on paragraph order
   (first = blurb, second = description). Accidentally adding a blank `<p>`
   or reordering paragraphs silently breaks field assignment. YAML has named
   keys — order doesn't matter.

3. **Lists and structured data are native.** Today `topics: python, programming`
   is a comma-separated string that gets split. In YAML, `[python, programming]`
   is a real list. The `services` field in after-school.md already uses YAML
   list syntax inside the code block — pure YAML would make this consistent.

4. **Simpler parser.** The current pipeline is: extract frontmatter → split on
   H1 → render markdown-it → parse HTML DOM → pop paragraphs by position →
   extract custom tags → parse YAML code block → merge → normalize. Pure YAML
   would be: `yaml.load()` → normalize. Dramatically simpler.

5. **No HTML in source content.** Currently `<content>`, `<enroll>`, etc.
   contain markdown that gets rendered to HTML, and some records have raw
   `<p>` tags mixed in. YAML would store plain text (or markdown strings),
   with HTML rendering happening at build time.

6. **Schema validation is straightforward.** YAML maps directly to JSON Schema.
   You could validate with standard tools instead of custom DOM-based extraction.

7. **Data-only records are much cleaner.** Person records, CTAs, categories —
   things that are basically structured data with no rich prose — are awkward
   as markdown. They'd be natural as YAML.

### What gets WORSE in YAML

1. **Long prose is less pleasant to write.** The `content` field often has
   multiple sentences or paragraphs of marketing copy. In YAML you'd use
   block scalars (`>` or `|`), which work but:
   - You lose markdown formatting within content (bold, links, lists)
   - Indentation is syntactically significant, so pasting prose requires care
   - Editors don't give you markdown preview inside a YAML string

2. **Markdown rendering inside fields.** Some `<content>` blocks contain
   markdown lists, links, and formatting. In YAML these would be strings
   containing markdown, which then need a separate render step. This works
   (it's what most headless CMS systems do) but it's a "markdown inside YAML"
   situation that can feel awkward.

3. **The `<Include>` mechanism needs rethinking.** Today `<Include slug="x" field="y">`
   appears inside markdown body text. In YAML you'd need a convention like
   `content: !include x.content` or a post-processing step that resolves
   string templates.

4. **Multi-record files get long.** `weekly.md` has ~20 class records. As YAML,
   each record's prose fields would be indented under the list item, making
   the file harder to navigate. The H1 headings in markdown act as natural
   visual separators; YAML's `- slug:` entries are subtler.

5. **Editing tooling.** Markdown files get rich editor support (preview, syntax
   highlighting for prose, spell check). YAML editors treat content as data,
   not prose. People editing class descriptions would lose the "writing"
   experience.

6. **Content with special characters.** YAML requires quoting/escaping for
   strings containing `: `, `#`, `[`, etc. Class descriptions with colons
   or hashtags would need careful quoting. Today markdown handles this
   transparently.

### The mixed middle ground

The current format is honestly **already close to YAML** — the structured
metadata block IS YAML. The question is really about the prose fields
(blurb, description, content, enroll). For records that are mostly data
(people, CTAs, categories), YAML would be strictly better. For records
that are mostly prose (class descriptions, program pages), it would be
a downgrade in editing ergonomics.

---

## Verdict

| Dimension | Markdown (current) | Pure YAML |
|---|---|---|
| Editing prose | Good (native markdown) | Worse (strings in YAML) |
| Editing metadata | Fine (YAML code block) | Better (native) |
| Format consistency | Poor (3 different zones) | Good (one format) |
| Parser complexity | High (DOM + position + YAML) | Low (yaml.load) |
| Data-only records | Awkward | Natural |
| Rich content (links, lists) | Native | Markdown-in-YAML strings |
| Validation | Custom code | Standard JSON Schema |
| Include/template system | Works inline | Needs new convention |
| Visual scanning | H1 headings are clear | List items are dense |

**Bottom line:** The conversion is technically straightforward — there's no
data that can't be represented in YAML. The tradeoff is entirely about
*editing experience*. If most edits are to metadata fields (dates, slugs,
topics, prices), YAML wins. If most edits are to prose (descriptions,
content blocks), markdown is more natural. A hybrid like the current format
(or frontmatter-based systems like Astro's built-in content collections)
exists precisely because neither pure format handles both well.

A pragmatic option would be to move data-heavy record types (people, CTAs,
enrollments, categories) to YAML while keeping prose-heavy types (classes,
programs) in markdown — but that adds format diversity rather than reducing it.


---

## Hook Debug Info

```json
{
  "hook_payload": {
    "session_id": "7c8d156b-21d9-4b69-ba6d-7347f237f2e9",
    "transcript_path": "/Users/eric/.claude/projects/-Users-eric-proj-ai-project-clasi/7c8d156b-21d9-4b69-ba6d-7347f237f2e9.jsonl",
    "cwd": "/Users/eric/proj/ai-project/clasi",
    "permission_mode": "default",
    "hook_event_name": "PostToolUse",
    "tool_name": "ExitPlanMode",
    "tool_input": {},
    "tool_response": {
      "plan": null,
      "isAgent": false,
      "filePath": "/Users/eric/.claude/plans/elegant-honking-firefly.md"
    },
    "tool_use_id": "toolu_01Xk42NmuAX8bFCDrNqLUsHn"
  },
  "env": {
    "TOOL_INPUT": "",
    "TOOL_NAME": "",
    "SESSION_ID": "",
    "CLASI_AGENT_TIER": "",
    "CLASI_AGENT_NAME": "",
    "CLAUDE_PROJECT_DIR": "/Users/eric/proj/ai-project/clasi",
    "PWD": "/Users/eric/proj/ai-project/clasi",
    "CWD": ""
  },
  "plans_dir": "/Users/eric/.claude/plans",
  "plan_file": "/Users/eric/.claude/plans/mighty-painting-globe.md",
  "cwd": "/Users/eric/proj/ai-project/clasi"
}
```
