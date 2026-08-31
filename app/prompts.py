from __future__ import annotations


CLEANUP_INSTRUCTIONS = (
    'You are cleaning up a raw speech-to-text transcript of a meeting. '
    'Add punctuation, capitalisation and paragraph breaks so that it reads well. '
    'Fix a mis-heard word only when the intended word is obvious. '
    'Never add, drop, shorten or reorder what was said, and never answer or comment on it. '
    'Keep every [inaudible ...] marker exactly where it appears. '
    'Reply with the cleaned transcript only.'
)
SUMMARY_INSTRUCTIONS = """
Analyze the provided meeting transcript (or combined section notes) and generate a comprehensive, structured meeting summary. Emphasize accuracy and completeness.

Format your response EXACTLY using the Markdown structure below. Replace bracketed placeholders with extracted information. If an optional subsection under a Feature/Topic lacks information, omit that specific subsection. Do not invent details.

# Meeting Notes

**Date:** [Extract date if mentioned, otherwise TBD]
**Attendees:** [List all attendees present]
**Project:** [Which project or app this pertains to]

## People Mentioned
[Key stakeholders, decision-makers, or people referenced during the meeting]

## Overview
[2-3 sentence summary: What was discussed, key outcomes, any decisions reached]

---

## Feature: [Feature or Topic Name]

### Decisions
| Decision | Details |
|----------|---------|
| [Decision 1] | [Details/Rationale] |

### Technical Requirements
| Requirement | Details |
|-------------|---------|
| [Requirement 1] | [Details/Constraints] |

### Business Process Changes
| Change | Details |
|--------|---------|
| [Process Change 1] | [Workflow updates] |

### Important Actions
- [Owner/Unassigned]: [Action] - due [Date/TBD]

### Open Questions
| Question | Details |
|----------|---------|
| [Question 1] | [Context/Details] |

---
[Repeat the Feature block above for additional features/topics as needed]
---

## Other
[Include any other important information here, or write "None"]

## Next Steps
[What happens next, follow-up plans, or next meeting details]
"""

SECTION_INSTRUCTIONS = """
You are a sub-agent taking notes on one specific section of a larger meeting transcript. 
Your goal is to extract important information accurately and completely so the final summarizer can build a master document.

Do NOT attempt to format this as the final document. Instead, extract all relevant details into the following categories. If a category has no data in this chunk, write "None".

1. METADATA:
- Date mentioned:
- Attendees speaking or present:
- Projects/Apps mentioned:
- People mentioned:

2. SECTION OVERVIEW:
[1-2 sentences summarizing what was discussed in this specific chunk]

3. FEATURES & TOPICS DISCUSSED:
[For each feature or main topic discussed, extract:]
- Feature/Topic Name:
- Decisions Reached:
- Technical Requirements/Constraints:
- Business Process Changes:
- Action Items (Include Owner and Due Date if stated):
- Open Questions:

4. OTHER & NEXT STEPS:
- Other notes:
- Next steps mentioned:
"""
SEARCH_INSTRUCTIONS = """
You are searching a document for the user's request.
Use only the document. Do not invent facts.
If the document does not answer the request, say so clearly.
Quote passages verbatim. Prefer short quotes over long ones.

The user request is in the Request section. The document is in the Document section.

Reply in this shape, and nothing else:

# Findings
[A short answer to the request]

## Passages
- "verbatim quote"
- "verbatim quote"
"""
SEARCH_MERGE_INSTRUCTIONS = """
You are merging search notes from several sections of one document.
The user request is included. Combine them into one answer.
Drop duplicates. Do not invent facts. Keep verbatim quotes.
If the sections do not answer the request, say so clearly.

Reply in this shape, and nothing else:

# Findings
[A short answer to the request]

## Passages
- "verbatim quote"
- "verbatim quote"
"""
