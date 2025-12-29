# Run Flow Refactor Plan

Goal: simplify the CLI run flow by isolating concerns (selection, planning, execution, postrun) while preserving behavior.

## Phases

### Phase 1: Pipeline results (no behavior change)
- Introduce dataclasses to represent outputs of each stage:
  - SelectionResult
  - PlanResult
  - ExecutionResult
  - PostrunResult
- Refactor stage functions to return these objects instead of mutating shared state.

### Phase 2: Executor core vs UI
- Split execution into:
  - `executor_core.py`: pure execution loop, progress events, result aggregation
  - `executor_ui.py`: Rich-based progress sink
- `executor.py` becomes thin wiring.

### Phase 3: Planning decomposition
- Split planner responsibilities into:
  - `schedule_builder.py`: build base schedule (topics × pairs × reps)
  - `resume_filter.py`: filter out completed debates
  - `judge_allocator.py`: assign judges based on balancing rules
- `planner.py` coordinates modules and handles dry-run output.

### Phase 4: Selection normalization
- Introduce `RunMode` enum: STANDARD, QUICK_TEST, JUDGES_TEST, INCREMENTAL
- Move selection flow to a single resolver that dispatches by mode.

### Phase 5: Flag cleanup (optional, if safe)
- Replace booleans with explicit enums where possible:
  - `--side-policy {balanced, random, fixed}` replaces `--balanced-sides` + `--swap-sides`
  - `--judge-policy {balanced, random}` replaces `--balanced-judges/--random-judges`
  - `--ui {wizard, prompts, none}` replaces `--tui-wizard` + `--topic-select`
- Consider replacing `--apply-stage-token-limits` with `--stage-max-tokens` (explicit value).
- Consider moving `--postupload*` to a dedicated command if run flags get too crowded.

## Notes
- Preserve CLI as primary integration point.
- Keep OpenRouter-only model path.
- No behavior changes without explicit sign-off.
