# Build State Schema

Build states are serializable records produced by the M1.3 legal build engine.

## Fields

- `class_name`: CoA class name.
- `selected_ranks`: paid selected nodes as `{node_id, rank}` records.
- `free_node_ids`: zero-cost starting/passive nodes auto-included by legal closure.
- `ae_spent`: total Ability Essence spent by paid selections.
- `te_spent`: total Talent Essence spent by paid selections.
- `tab_ae`: per-tab Ability Essence spend.
- `tab_te`: per-tab Talent Essence spend.

## Rank Model

If a selected node omits rank, rank defaults to `1`. Cost is currently multiplied by selected rank. This is an intentional M1.3 model until official per-rank cost behavior is validated against builder UI examples.

## Validation Output

Validation returns `valid`, `state`, `issues`, and `warnings`. Issue objects include stable `code` values for tests and downstream reporting.
