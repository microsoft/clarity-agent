/** Glossary of clarity-agent terms for tooltip display. */
const GLOSSARY: Record<string, string> = {
  Protocol:
    "The structured set of documents that capture your project's thinking: problem, solution, architecture, and failure analysis.",
  Packet:
    "A shareable document generated from your protocol — a snapshot of your project's current state for stakeholders.",
  Stale:
    "A document whose dependencies have changed since it was last updated. It may need revision.",
  Current:
    "A document that is up-to-date with all its dependencies.",
  Process:
    "A guided thinking step (e.g. Problem Clarification, Failure Analysis) that produces or updates protocol documents.",
  Tier:
    "A model quality level (Thorough, Balanced, Quick) that controls which AI model is used for a process.",
  Transcript:
    "A saved record of a conversation session, including all messages and tool usage.",
  Session:
    "An active conversation with the Clarity Agent. Starting a new session resets the conversation context.",
  Documents:
    "The individual markdown files in your protocol that capture different aspects of your project.",
  "Review Packet":
    "A compiled document you can share with stakeholders, generated from your protocol documents.",
  Status:
    "An overview of which protocol documents are current, stale, or missing.",
};

export default GLOSSARY;
