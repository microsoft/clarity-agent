# Responsible AI FAQ

## What is the Clarity Agent?

The Clarity Agent is a tool designed to help you figure out how to solve problems by turning an AI
into a dialogue partner that understands a wide range of methods for resolving tricky situations,
clarifying problems, and planning for what could go wrong.

## What can Clarity Agent do?

You can use Clarity Agent in two ways:

- As a **standalone chat experience** via a desktop Mac or Windows app, or a local web app for the
  more technically minded. This lets you create any kind of project, from a business idea to a
  research plan to just wanting to make progress on something important. It will work with you to build and
  refine a plan, and can help you write up the plan in a crisp way so you can work with others if
  needed.
- By **integrating it in a coding agent** or a similar agentic experience; the Agent can be
  integrated either as a local MCP server that you add to your agent, or by generating an AGENTS.md
  file that lets your agent use it directly. It will do the same kind of dialogue to help you design
  your software project — with its files now living in the `.clarity-protocol` subdirectory of your
  repository — and those output files can further help your coding agent build what you're
  designing.
  
In both cases, you need to bring your own model — you can use Clarity Agent with all sorts of LLMs,
including Azure, GitHub Copilot, OpenAI, and Anthropic.

## What are Clarity Agent’s intended use(s)? 

The system is intended to work for a wide range of problems. In the first version, it's focused on
things that take the form of "I have a problem, and I want to do something concrete to solve it;"
more open-ended problems like "I have a problem, and need to figure out what a solution even means"
are only partially supported.

## How was Clarity Agent evaluated? What metrics are used to measure performance?

So far, the Clarity Agent has been hand-tested by humans. Our goal for its OSS release is to give
more people a chance to play with it, so we can figure out if it does indeed work, and then tune it.

We also have a structured, automated evaluation system as part of the codebase, that tests both its
functionality (does it give good advice?) and safety (does it not, for example, help people get
clarity about how to commit a better murder?). You can find the full evaluation framework, test
cases, and the most recent evaluation results in the evals/ directory.

## What are the limitations of Clarity Agent? How can users minimize the impact of Clarity Agent’s limitations when using the system?

This is an early release, and there are likely cases where the experience falls short.
Take all of its outputs with a grain of salt.

Two important things you can do to get the best possible results:

1. **Engage in dialogue:** The Clarity Agent will ask you questions and propose plans. Read through
   what it says and tell it what you agree with, what you're unsure about, or what you'd change. The
   more actively you engage, the better the results.
2. **Use a capable model:** Clarity Agent benefits from the most powerful models available. You'll
   see a meaningful quality difference when using frontier models with deep reasoning capabilities.

## What operational factors and settings allow for effective and responsible use of Clarity Agent?

Clarity Agent works best when you bring domain knowledge to the conversation. A software engineer
brainstorming a software project will get more out of it than someone with no software background.
This isn't unique to Clarity Agent — AI tools in general augment existing expertise rather than
replacing it.

Because Clarity Agent works through close dialogue with you, it is less susceptible to problems
like hallucination or drift than a tool that generates output without interaction. That said,
review its suggestions critically, especially for consequential decisions.

## How do I provide feedback on Clarity Agent?

Please share feedback by filing an issue on our GitHub repository:
<https://github.com/microsoft/clarity-agent/issues>. Bug reports, feature requests, and general
impressions are all welcome.

## Does Clarity Agent collect telemetry?

No. Clarity Agent does not collect telemetry, usage data, or any other information about you or
your sessions. Everything you do with Clarity Agent — your conversations, your protocol files, your
project content — stays on your machine (and goes to whichever LLM provider you have configured,
under that provider's terms).
