import json
import logging
import re
import time

import pandas as pd

# Orchestrates the full annotation pipeline. Lower-level modules own organism
# resolution, paper retrieval, model prompting, and metadata construction; this
# function keeps those contracts in one linear flow so CLI and web jobs share
# the same behavior.
from . import llms
from . import gene_names
from . import metadata
from . import organisms
from . import pmc
from . import targets
from . import utils

from .models import MODEL_SUMMARY, MODEL_AGGREGATION, MODEL_CONSENSUS

logging.basicConfig(format='%(asctime)s %(levelname).1s | %(message)s')
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def _safe_mapping_component(value):
    component = re.sub(r'[^A-Za-z0-9._-]+', '_', str(value).strip())
    component = re.sub(r'\.+', '.', component).strip('._-')
    return component or 'target'


def _pmc_mapping_cache_key(profile, target):
    identifier = _safe_mapping_component(target.primary_identifier)
    if profile.profile_id == 'mtb-h37rv' and target.resolved_locus:
        return identifier
    profile_component = _safe_mapping_component(profile.profile_id)
    return f'{profile_component}__{identifier}'


def _profile_lookup_from_config(profile_config):
    if not profile_config or profile_config.get('source') == 'builtin':
        return None

    identifiers = [
        profile_config.get('profile_id'),
        profile_config.get('canonical_name'),
        *(profile_config.get('synonyms') or ()),
    ]
    normalized_identifiers = {
        organisms.normalize_identifier(str(identifier))
        for identifier in identifiers
        if identifier
    }

    def lookup_profile(profile_identifier):
        if profile_identifier is None:
            return None
        normalized_identifier = organisms.normalize_identifier(str(profile_identifier))
        if normalized_identifier in normalized_identifiers:
            return profile_config
        return None

    return lookup_profile


def get_gene_annotation(
    gene=None, cache_dir='./.cache', profile=None, profile_config=None, organism=None, strain=None,
    locus=None, name=None, gene_name_cache_dir=gene_names.DEFAULT_GENE_NAME_CACHE_DIR,
    allow_online_name_lookup=True, refresh_gene_name_cache=False,
    cache_supplied_name=False,
):
    if locus is None and gene is not None:
        locus = gene
    if profile is None and organism is None:
        profile = 'mtb-h37rv'
    target = targets.resolve_annotation_target(
        profile_identifier=profile,
        organism_identifier=organism,
        strain_identifier=strain,
        locus=locus,
        name=name,
        profile_lookup=_profile_lookup_from_config(profile_config),
        gene_name_cache_dir=gene_name_cache_dir,
        allow_online_name_lookup=allow_online_name_lookup,
    )
    gene = target.resolved_locus
    name = target.resolved_name
    display_gene = target.primary_identifier
    profile_context = target.profile

    gene_name_source = target.gene_name_source
    gene_name_source_detail = target.gene_name_source_detail
    gene_name_confidence = target.gene_name_confidence
    gene_name_aliases = target.gene_name_aliases
    gene_name_candidates = target.gene_name_candidates
    gene_name_warnings = target.gene_name_warnings

    if target.submitted_name is not None:
        gene_name_source = gene_name_source or 'supplied'
        gene_name_source_detail = gene_name_source_detail or 'supplied argument'
        gene_name_confidence = gene_name_confidence or 'curator_supplied'
        if cache_supplied_name and gene is not None and name:
            gene_names.cache_supplied_gene_name(
                profile_context,
                gene,
                name,
                cache_dir=gene_name_cache_dir,
            )
    elif refresh_gene_name_cache and gene is not None:
        lookup_result = gene_names.resolve_gene_name(
            profile_context,
            gene,
            cache_dir=gene_name_cache_dir,
            allow_online_lookup=allow_online_name_lookup,
            refresh_cache=True,
        )
        name = lookup_result.gene_name
        gene_name_source = lookup_result.source
        gene_name_source_detail = lookup_result.source_detail
        gene_name_confidence = lookup_result.confidence
        gene_name_aliases = list(lookup_result.aliases)
        gene_name_candidates = list(lookup_result.candidates)
        gene_name_warnings = list(lookup_result.warnings)

    log.info(
        f'Starting annotation process for {profile_context.canonical_name} gene {display_gene}'
    )
    start = time.time()
    llm_handler = llms.LlmHandler(cache_dir)
    paper_manager = pmc.PmcPaperManager(cache_dir, organism_profile=profile_context)

    ranked_papers = paper_manager.get_ranked_papers(gene, name)
    pmc_ids = [record.pmc_id for record in ranked_papers]
    paper_manager.save_gene_pmc_ids(_pmc_mapping_cache_key(profile_context, target), pmc_ids)
    section_distillation_candidates = []
    section_distillations = []

    if len(pmc_ids) < 3:
        log.warning(
            f'Found only {len(pmc_ids)} paper{utils.s_if_plural(pmc_ids)} for gene {display_gene}'
        )

    # Selection happens before any LLM calls because each analyzed section is
    # expensive: three model summaries, one consensus call, then final
    # aggregation. Keep ranking changes in pmc/metadata so this orchestration
    # remains about pipeline order rather than relevance policy.
    selection = paper_manager.select_relevance_records(
        ranked_papers,
        target_relevance=pmc.DEFAULT_TARGET_RELEVANCE,
        min_score=pmc.DEFAULT_MIN_SCORE,
        max_rank=pmc.DEFAULT_MAX_RANK,
        min_papers=pmc.DEFAULT_MIN_PAPERS,
        max_papers=pmc.DEFAULT_MAX_PAPERS,
    )
    papers_to_analyze = [record.pmc_id for record in selection.selected_records]
    cumulative_relevance = selection.cumulative_relevance

    if selection.selection_mode == metadata.SELECTION_MODE_LIMITED:
        log.warning(
            f'Limited literature for gene {display_gene}: analyzing all '
            f'{len(papers_to_analyze)} eligible paper{utils.s_if_plural(papers_to_analyze)} '
            f'(fewer than minimum {pmc.DEFAULT_MIN_PAPERS})'
        )

    used = []
    relevance_by_pmc_id = {
        record.pmc_id: record
        for record in ranked_papers
    }

    for pmc_id in papers_to_analyze:
        sections = []

        # The annotator currently distills only abstract, results, and
        # discussion. Methods are cached by the paper parser, but left out of
        # annotation because they usually describe experimental setup rather
        # than gene-level biological claims.
        relevance_record = relevance_by_pmc_id.get(pmc_id)
        relevance_score = relevance_record.score if relevance_record is not None else 0.0
        log.info(
            f'Starting inference process for gene {display_gene} with paper PMC{pmc_id} '
            f'(relevance score {relevance_score:.3f})'
        )
        used.append(pmc_id)

        abstract = paper_manager.get_abstract(pmc_id)
        if abstract is not None:
            sections.append(('abstract', abstract))
        results = paper_manager.get_results(pmc_id)
        if results is not None:
            sections.append(('results', results))
        discussion = paper_manager.get_discussion(pmc_id)
        if discussion is not None and discussion != results:
            sections.append(('discussion', discussion))

        log.debug(
            f'Obtained {len(sections)} relevant section{utils.s_if_plural(sections)} for ' + \
                f'paper PMC{pmc_id}'
        )

        for label, section in sections:
            log.debug(f'Starting processing for PMC{pmc_id} {label}')
            section_distillation_candidates_cur = []
            llm_gene = gene
            llm_name = name or display_gene
            # Consensus assumes exactly three independent candidates. Model
            # configuration enforces that cardinality, so callers should change
            # the consensus interface before changing the number of summaries.
            for model in (MODEL_SUMMARY): #for model in ('mistral-nemo:12b', 'llama3:8b', 'gemma3:12b'):
                section_distillation_candidate, duration_sec = llm_handler.get_llm_gene_info_json(
                    llm_gene, llm_name, section, model, section_type=label,
                    organism_profile=profile_context,
                )
                section_distillation_candidates_cur.append(section_distillation_candidate)
                section_distillation_candidates.append((
                    f'PMC{pmc_id}', label, model, llm_gene, llm_name, section_distillation_candidate,
                    duration_sec
                ))
            section_distillation, duration_sec = llm_handler.get_llm_consensus_json(
                section_distillation_candidates_cur[0], section_distillation_candidates_cur[1],
                section_distillation_candidates_cur[2], model=MODEL_CONSENSUS,
                section_type=label, organism_profile=profile_context,
                allow_missing_locus=gene is None,
            )
            section_distillations.append((
                f'PMC{pmc_id}', label, MODEL_CONSENSUS, llm_gene, llm_name,
                section_distillation, duration_sec
            ))

    section_distillation_candidate_df = pd.DataFrame(
        section_distillation_candidates,
        columns=['PmcId', 'SectionType', 'Model', 'Gene', 'GeneName', 'Response', 'LlmDur'],
    )

    section_distillation_df = pd.DataFrame(
        section_distillations,
        columns=['PmcId', 'SectionType', 'Model', 'Gene', 'GeneName', 'Response', 'LlmDur'],
    )
    log.debug(' '.join((
        'Finished paper distillation by LLM with',
        str(len(section_distillation_candidate_df)),
        'total summaries generated for',
        str(len(section_distillation_df)),
        f'total paper section{utils.s_if_plural(section_distillation_df)} for gene',
        display_gene
    )))
    # The dataframes are temporary bookkeeping for prompt construction,
    # filtering, and metadata. They are not part of a persisted schema.
    section_distillation_df.insert(
        1, 'PMID', section_distillation_df['PmcId'].map(paper_manager.get_pmid)
    )

    # This filter is a structural sanity check only: parseable JSON and profile-
    # appropriate gene identity. It does not verify biological correctness.
    section_distillation_filtered_df = section_distillation_df.loc[
        section_distillation_df['Response'].map(
            lambda response: llm_handler.json_regex_filter(
                response,
                organism_profile=profile_context,
                expected_gene=gene,
            )
        ),
        :
    ]
    log.debug(
        f'Filtered down to {len(section_distillation_filtered_df)} valid ' +\
            f'section{utils.s_if_plural(section_distillation_filtered_df)} for gene {display_gene}'
    )

    pmids_analyzed = []
    if len(section_distillation_filtered_df) > 0:
        pmids_analyzed = [
            str(pmid) for pmid in section_distillation_filtered_df['PMID'].dropna().unique()
        ]

    literature_context = metadata.build_literature_context_for_notes(
        ranked_records=ranked_papers,
        selected_records=selection.selected_records,
        selection_mode=selection.selection_mode,
        eligible_count=selection.eligible_count,
        cumulative_relevance=cumulative_relevance,
        target_relevance=pmc.DEFAULT_TARGET_RELEVANCE,
        min_papers=pmc.DEFAULT_MIN_PAPERS,
    )

    if len(section_distillation_filtered_df) >= 1:
        def _relevance_for_pmc_label(pmc_label):
            pmc_id = str(pmc_label).removeprefix('PMC')
            record = relevance_by_pmc_id.get(pmc_id)
            return record.score if record is not None else None

        # Relevance scores and literature context are passed into the aggregate
        # prompt so final notes can expose confidence and selection limitations
        # instead of presenting every generated field as equally supported.
        relevance_scores = section_distillation_filtered_df['PmcId'].map(_relevance_for_pmc_label)
        gene_distillation, duration_sec = llm_handler.get_llm_aggregate_json(
            section_distillation_filtered_df['Response'],
            section_distillation_filtered_df['PMID'],
            model=MODEL_AGGREGATION,
            literature_context=literature_context,
            relevance_scores=relevance_scores.tolist(),
            organism_profile=profile_context,
            allow_missing_locus=gene is None,
        )
    else:
        gene_distillation = None

    duration = time.time() - start
    log.info(
        f'Finished annotation process for gene {display_gene} in {utils.seconds_to_str(duration)}'
    )

    llm_usage = llm_handler.summarize_usage()

    annotation_metadata = metadata.build_annotation_metadata(
        gene=gene,
        gene_name=name,
        ranked_records=ranked_papers,
        selected_records=selection.selected_records,
        analyzed_pmc_ids=used,
        pmids_analyzed=pmids_analyzed,
        sections_analyzed=len(section_distillation_filtered_df),
        selection_mode=selection.selection_mode,
        eligible_count=selection.eligible_count,
        cumulative_relevance=cumulative_relevance,
        target_relevance=pmc.DEFAULT_TARGET_RELEVANCE,
        min_papers=pmc.DEFAULT_MIN_PAPERS,
        max_papers=pmc.DEFAULT_MAX_PAPERS,
        duration_sec=duration,
        profile_id=profile_context.profile_id,
        canonical_name=profile_context.canonical_name,
        species_name=profile_context.species_name,
        strain=profile_context.strain,
        gene_name_source=gene_name_source,
        gene_name_source_detail=gene_name_source_detail,
        gene_name_candidates=gene_name_candidates,
        gene_name_confidence=gene_name_confidence,
        gene_name_aliases=gene_name_aliases,
        gene_name_warnings=gene_name_warnings,
        submitted_locus=target.submitted_locus,
        submitted_name=target.submitted_name,
        resolved_locus=target.resolved_locus,
        resolved_name=target.resolved_name,
        profile_source=target.profile_source,
        target_warnings=target.warnings,
        llm_usage=llm_usage,
    )

    merged_annotation = None
    if gene_distillation is not None:
        field_coverage = metadata.build_field_coverage(json.loads(gene_distillation))
        merged_annotation = metadata.merge_annotation_output(
            gene_distillation,
            annotation_metadata,
            field_coverage=field_coverage,
        )

    return {
        "gene_distillation": gene_distillation,
        "gene_annotation": merged_annotation,
        "pmc_ids": pmc_ids,
        "used_ids": used,
        "cumulative_relevance": cumulative_relevance,
        "selection_mode": selection.selection_mode,
        "annotation_metadata": annotation_metadata,
    }
