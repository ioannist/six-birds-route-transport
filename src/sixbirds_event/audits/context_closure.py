from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from ..schemas.event_package import EventPackageInstance
from ..schemas.observation_trace import ObservationTrace, RepeatedReadSequence


@dataclass(slots=True)
class CCDContextResult:
    context_id: str
    ccd: float | None
    exclusivity_defect: float
    exhaustivity_defect: float
    reread_instability: float | None
    closure_defect: float | None
    total_read_steps: int
    valid_singleton_steps: int
    valid_singleton_transitions: int
    transition_counts: dict[str, dict[str, int]]
    insufficient_transition_data: bool


@dataclass(slots=True)
class ContextClosureDefectResult:
    trace_id: str
    instance_id: str | None
    overall_ccd: float | None
    context_results: list[CCDContextResult]
    component_weights: dict[str, float]
    insufficient_data_contexts: list[str]


def _context_atom_ids(
    instance: EventPackageInstance | None,
) -> dict[str, list[str]] | None:
    if instance is None:
        return None
    return {
        context.context_id: [atom.atom_id for atom in context.atoms]
        for context in instance.contexts
    }


def _group_sequences_by_context(
    sequences: list[RepeatedReadSequence],
) -> dict[str, list[RepeatedReadSequence]]:
    grouped: dict[str, list[RepeatedReadSequence]] = defaultdict(list)
    for sequence in sequences:
        grouped[sequence.context_id].append(sequence)
    return dict(grouped)


def _transition_counts(
    sequences: list[RepeatedReadSequence],
) -> Counter[tuple[str, str]]:
    counts: Counter[tuple[str, str]] = Counter()
    for sequence in sequences:
        for left, right in zip(sequence.reads, sequence.reads[1:], strict=False):
            if len(left) == 1 and len(right) == 1:
                counts[(left[0], right[0])] += 1
    return counts


def _row_distribution(
    *,
    source_atom: str,
    atoms: list[str],
    counts: Counter[tuple[str, str]],
) -> dict[str, float]:
    total = sum(counts[(source_atom, target_atom)] for target_atom in atoms)
    if total == 0:
        return {
            target_atom: 1.0 if target_atom == source_atom else 0.0
            for target_atom in atoms
        }
    return {
        target_atom: counts[(source_atom, target_atom)] / total for target_atom in atoms
    }


def _tv_distance(
    left: dict[str, float], right: dict[str, float], atoms: list[str]
) -> float:
    return 0.5 * sum(abs(left[atom] - right[atom]) for atom in atoms)


def _closure_defect(
    *,
    atoms: list[str],
    counts: Counter[tuple[str, str]],
) -> float | None:
    outgoing_counts = {
        atom: sum(counts[(atom, target)] for target in atoms) for atom in atoms
    }
    total_outgoing = sum(outgoing_counts.values())
    if total_outgoing == 0:
        return None

    kernel = {
        atom: _row_distribution(source_atom=atom, atoms=atoms, counts=counts)
        for atom in atoms
    }
    defect = 0.0
    for atom in atoms:
        if outgoing_counts[atom] == 0:
            continue
        squared = {
            target: sum(kernel[atom][mid] * kernel[mid][target] for mid in atoms)
            for target in atoms
        }
        weight = outgoing_counts[atom] / total_outgoing
        defect += weight * _tv_distance(kernel[atom], squared, atoms)
    return defect


def _context_result(
    *,
    context_id: str,
    sequences: list[RepeatedReadSequence],
    atoms: list[str],
    component_weights: dict[str, float],
) -> CCDContextResult:
    all_reads = [read for sequence in sequences for read in sequence.reads]
    total_steps = len(all_reads)
    multi_outcome_steps = sum(1 for read in all_reads if len(read) > 1)
    empty_steps = sum(1 for read in all_reads if len(read) == 0)
    valid_singleton_steps = sum(1 for read in all_reads if len(read) == 1)

    counts = _transition_counts(sequences)
    total_transitions = sum(counts.values())
    changed_transitions = sum(
        count for (left, right), count in counts.items() if left != right
    )
    reread_instability = (
        changed_transitions / total_transitions if total_transitions > 0 else None
    )
    closure_defect = _closure_defect(atoms=atoms, counts=counts)

    components = {
        "exclusivity_defect": multi_outcome_steps / total_steps
        if total_steps > 0
        else 0.0,
        "exhaustivity_defect": empty_steps / total_steps if total_steps > 0 else 0.0,
        "reread_instability": reread_instability,
        "closure_defect": closure_defect,
    }
    available = [value for value in components.values() if value is not None]
    ccd = sum(available) / len(available) if available else None

    transition_counts: dict[str, dict[str, int]] = {}
    for atom in atoms:
        row = {
            target: counts[(atom, target)]
            for target in atoms
            if counts[(atom, target)] > 0
        }
        if row:
            transition_counts[atom] = row

    return CCDContextResult(
        context_id=context_id,
        ccd=ccd,
        exclusivity_defect=components["exclusivity_defect"],
        exhaustivity_defect=components["exhaustivity_defect"],
        reread_instability=reread_instability,
        closure_defect=closure_defect,
        total_read_steps=total_steps,
        valid_singleton_steps=valid_singleton_steps,
        valid_singleton_transitions=total_transitions,
        transition_counts=transition_counts,
        insufficient_transition_data=total_transitions == 0,
    )


def compute_context_closure_defect(
    trace: ObservationTrace,
    *,
    instance: EventPackageInstance | None = None,
) -> ContextClosureDefectResult:
    component_weights = {
        "exclusivity_defect": 0.25,
        "exhaustivity_defect": 0.25,
        "reread_instability": 0.25,
        "closure_defect": 0.25,
    }
    atoms_by_context = _context_atom_ids(instance)
    grouped = _group_sequences_by_context(trace.repeated_read_sequences)
    context_results: list[CCDContextResult] = []

    for context_id in sorted(grouped):
        if atoms_by_context is not None:
            atoms = atoms_by_context[context_id]
        else:
            observed_atoms = sorted(
                {
                    atom_id
                    for sequence in grouped[context_id]
                    for read in sequence.reads
                    for atom_id in read
                }
            )
            atoms = observed_atoms
        context_results.append(
            _context_result(
                context_id=context_id,
                sequences=grouped[context_id],
                atoms=atoms,
                component_weights=component_weights,
            )
        )

    available_ccd = [result.ccd for result in context_results if result.ccd is not None]
    overall_ccd = sum(available_ccd) / len(available_ccd) if available_ccd else None
    insufficient_data_contexts = [
        result.context_id
        for result in context_results
        if result.insufficient_transition_data
    ]
    return ContextClosureDefectResult(
        trace_id=trace.trace_id,
        instance_id=trace.instance_id if instance is None else instance.instance_id,
        overall_ccd=overall_ccd,
        context_results=context_results,
        component_weights=component_weights,
        insufficient_data_contexts=insufficient_data_contexts,
    )
