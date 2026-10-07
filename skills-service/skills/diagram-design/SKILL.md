---
name: diagram-design
description: >
  Produce clean, well-structured diagrams (architecture, flowchart, sequence,
  ER) in Mermaid syntax. Use when the user asks for a diagram, visual
  explanation, or system overview. Based on cathrynlavery/diagram-design.
---

# Diagram Design

You design diagrams that are legible at a glance. Follow these rules when
producing any diagram.

## Syntax
- Always output valid **Mermaid** in a fenced ```mermaid block.
- Quote all node labels containing spaces, parentheses, or special chars:
  `A["User signs up"]`.
- Declare edge labels with `-->|"label"|` (quoted) to avoid parser errors.

## Layout
- Top-to-bottom (`graph TD`) for flows and decisions; left-to-right (`graph LR`)
  for pipelines and data flow; `sequenceDiagram` for request/response between
  2+ services; `erDiagram` for schemas.
- One idea per diagram. Split complex systems into layers instead of one giant
  graph.

## Content
- Node labels are verb phrases for actions ("Validate request") and noun
  phrases for entities ("Auth service") — never mix within a layer.
- Max ~12 nodes before splitting; group related nodes with `subgraph`.
- Every decision node has exactly two labeled exits (e.g. `|"yes"|`, `|"no"|`).
- Include the failure path. A flowchart without error handling is a wish, not
  a design.

## Review checklist before answering
1. Parses? (no unquoted specials, no circular subgraph refs)
2. Direction suits the content?
3. Every path terminates?
4. Labels readable at 14px?
