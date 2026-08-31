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
Analyze the provided meeting transcript and generate a structured summary by following these steps:

1. Identify the core purpose of the meeting, major conclusions reached, and open discussions.
2. Extract every explicit commitment, assignment, or follow-up item.

Provide your response in EXACTLY this structure:

SUMMARY
[A brief paragraph summarizing the high-level purpose and outcomes of the conversation.]
- [Key discussion point or decision 1]
- [Key discussion point or decision 2]
- [Key discussion point or decision 3]
- [etc as needed]

ACTION ITEMS
- [Owner/Unassigned]: [Clear description of task]
- [Owner/Unassigned]: [Clear description of task]
- [etc as needed]
(If no tasks exist, output strictly: "- None stated.")
"""
SECTION_INSTRUCTIONS = (
    'You are taking notes on one part of a longer meeting transcript. '
    'Please provide the following: \n' + SUMMARY_INSTRUCTIONS
)
