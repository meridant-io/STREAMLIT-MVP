from __future__ import annotations

def q_list_next_usecases(limit: int = 200) -> str:
    return f"SELECT id, usecase_title FROM Next_UseCase ORDER BY id LIMIT {int(limit)};"

def q_list_tags() -> str:
    return "SELECT id, tag_name, tag_description FROM Next_CapabilityTag ORDER BY tag_name;"

def q_get_usecase_intent(usecase_id: int) -> str:
    return f"""
    SELECT ui.id, ui.intent_tag_id AS tag_id, t.tag_name, ui.weight, ui.source, ui.created_on
    FROM Next_UseCaseIntent ui
    JOIN Next_CapabilityTag t ON ui.intent_tag_id = t.id
    WHERE ui.usecase_id = {int(usecase_id)}
    ORDER BY ui.weight DESC, t.tag_name;
    """

def w_replace_usecase_intent(usecase_id: int, tag_weights: dict[int, int], source: str = "ui") -> str:
    statements = [f"DELETE FROM Next_UseCaseIntent WHERE usecase_id={int(usecase_id)};"]
    for tag_id, weight in tag_weights.items():
        statements.append(
            f"INSERT INTO Next_UseCaseIntent (usecase_id, intent_tag_id, weight, source) "
            f"VALUES ({int(usecase_id)}, {int(tag_id)}, {int(weight)}, '{source.replace(\"'\",\"''\")}');"
        )
    return "\n".join(statements)

def q_discover_capabilities(usecase_id: int, limit: int = 50) -> str:
    return f"""
    SELECT
        c.id AS capability_id,
        c.capability_name,
        d.domain_name,
        sd.subdomain_name,
        COUNT(DISTINCT ui.intent_tag_id) AS relevance_score
    FROM Next_UseCaseIntent ui
    JOIN Next_CapabilityTagMap ctm ON ui.intent_tag_id = ctm.tag_id
    JOIN Next_Capability c ON ctm.capability_id = c.id
    JOIN Next_Domain d ON c.domain_id = d.id
    JOIN Next_SubDomain sd ON c.subdomain_id = sd.id
    WHERE ui.usecase_id = {int(usecase_id)}
    GROUP BY c.id
    ORDER BY relevance_score DESC, c.capability_name
    LIMIT {int(limit)};
    """

def w_init_target_maturity(usecase_id: int, dimension_id: int = 1, target_score: int = 3) -> str:
    return f"""
    INSERT INTO Next_TargetMaturity (usecase_id, capability_id, dimension_id, target_score)
    SELECT {int(usecase_id)}, c.id, {int(dimension_id)}, {int(target_score)}
    FROM Next_Capability c
    WHERE NOT EXISTS (
      SELECT 1 FROM Next_TargetMaturity tm
      WHERE tm.usecase_id = {int(usecase_id)} AND tm.capability_id = c.id AND tm.dimension_id = {int(dimension_id)}
    );
    """

def w_generate_roadmap(usecase_id: int) -> str:
    return f"""
    DELETE FROM Next_RoadmapStep WHERE usecase_id={int(usecase_id)};

    INSERT INTO Next_RoadmapStep (usecase_id, capability_id, phase, priority_score)
    SELECT
      {int(usecase_id)},
      ranked.capability_id,
      CASE
        WHEN ranked.priority_score >= 8 THEN 1
        WHEN ranked.priority_score >= 5 THEN 2
        WHEN ranked.priority_score >= 3 THEN 3
        ELSE 4
      END,
      ranked.priority_score
    FROM (
      SELECT
        c.id AS capability_id,
        COUNT(DISTINCT ui.intent_tag_id) AS intent_score,
        (tm.target_score - COALESCE(ma.maturity_score,0)) AS maturity_gap,
        COUNT(DISTINCT ci.target_capability_id) AS dependency_weight,
        (
          COUNT(DISTINCT ui.intent_tag_id)
          + (tm.target_score - COALESCE(ma.maturity_score,0))
          + COUNT(DISTINCT ci.target_capability_id)
        ) AS priority_score
      FROM Next_Capability c
      LEFT JOIN Next_CapabilityTagMap ctm ON c.id = ctm.capability_id
      LEFT JOIN Next_UseCaseIntent ui ON ui.intent_tag_id = ctm.tag_id AND ui.usecase_id = {int(usecase_id)}
      LEFT JOIN Next_TargetMaturity tm ON tm.capability_id = c.id AND tm.usecase_id = {int(usecase_id)}
      LEFT JOIN Next_MaturityAssessment ma ON ma.capability_id = c.id
      LEFT JOIN Next_CapabilityInterdependency ci ON ci.source_capability_id = c.id
      GROUP BY c.id
    ) ranked;
    """

def q_roadmap_phase_counts(usecase_id: int) -> str:
    return f"""
    SELECT phase, COUNT(*) AS capability_count
    FROM Next_RoadmapStep
    WHERE usecase_id={int(usecase_id)}
    GROUP BY phase
    ORDER BY phase;
    """

def w_generate_cluster_roadmap(usecase_id: int) -> str:
    return f"""
    DELETE FROM Next_RoadmapClusterStep WHERE usecase_id={int(usecase_id)};

    INSERT INTO Next_RoadmapClusterStep (usecase_id, cluster_id, phase, priority_score, capability_count)
    SELECT
      {int(usecase_id)},
      cm.cluster_id,
      CASE
        WHEN AVG(rs.priority_score) >= 8 THEN 1
        WHEN AVG(rs.priority_score) >= 5 THEN 2
        WHEN AVG(rs.priority_score) >= 3 THEN 3
        ELSE 4
      END,
      AVG(rs.priority_score),
      COUNT(*)
    FROM Next_RoadmapStep rs
    JOIN Next_CapabilityClusterMap cm ON rs.capability_id = cm.capability_id
    WHERE rs.usecase_id = {int(usecase_id)}
    GROUP BY cm.cluster_id;
    """

def q_cluster_roadmap(usecase_id: int) -> str:
    return f"""
    SELECT c.cluster_name, r.phase, r.capability_count, ROUND(r.priority_score,2) AS avg_priority
    FROM Next_RoadmapClusterStep r
    JOIN Next_CapabilityCluster c ON r.cluster_id=c.id
    WHERE r.usecase_id={int(usecase_id)}
    ORDER BY r.phase, r.priority_score DESC;
    """

def w_run_investment(usecase_id: int, budget: float) -> str:
    # MVP: records budget, selects top-20 by benefit/cost (unit cost model)
    return f"""
    INSERT INTO Next_InvestmentRun (usecase_id, budget, cost_model)
    VALUES ({int(usecase_id)}, {float(budget)}, 'default-unit-cost');

    DELETE FROM Next_InvestmentSelection
    WHERE run_id = (SELECT id FROM Next_InvestmentRun ORDER BY id DESC LIMIT 1);

    INSERT INTO Next_InvestmentSelection (run_id, capability_id, selected_order, estimated_cost, benefit_score, benefit_per_cost)
    SELECT
      (SELECT id FROM Next_InvestmentRun ORDER BY id DESC LIMIT 1),
      ranked.capability_id,
      ROW_NUMBER() OVER (ORDER BY ranked.benefit_per_cost DESC),
      ranked.estimated_cost,
      ranked.benefit_score,
      ranked.benefit_per_cost
    FROM (
      SELECT
        c.id AS capability_id,
        ic.estimated_cost,
        (
          COUNT(DISTINCT ui.intent_tag_id)
          + (tm.target_score - COALESCE(ma.maturity_score,0))
          + COUNT(DISTINCT ci.target_capability_id)
        ) AS benefit_score,
        (
          (
            COUNT(DISTINCT ui.intent_tag_id)
            + (tm.target_score - COALESCE(ma.maturity_score,0))
            + COUNT(DISTINCT ci.target_capability_id)
          ) / ic.estimated_cost
        ) AS benefit_per_cost
      FROM Next_Capability c
      JOIN Next_CapabilityInvestmentCost ic ON ic.capability_id = c.id
      LEFT JOIN Next_CapabilityTagMap ctm ON c.id = ctm.capability_id
      LEFT JOIN Next_UseCaseIntent ui ON ui.intent_tag_id = ctm.tag_id AND ui.usecase_id = {int(usecase_id)}
      LEFT JOIN Next_TargetMaturity tm ON tm.capability_id = c.id AND tm.usecase_id = {int(usecase_id)}
      LEFT JOIN Next_MaturityAssessment ma ON ma.capability_id = c.id
      LEFT JOIN Next_CapabilityInterdependency ci ON ci.source_capability_id = c.id
      GROUP BY c.id
    ) ranked
    WHERE ranked.benefit_per_cost > 0
    LIMIT 20;
    """

def q_latest_investment_selection(usecase_id: int) -> str:
    return f"""
    SELECT
      c.capability_name,
      s.selected_order,
      s.benefit_score,
      s.benefit_per_cost
    FROM Next_InvestmentSelection s
    JOIN Next_Capability c ON s.capability_id=c.id
    WHERE s.run_id = (SELECT id FROM Next_InvestmentRun WHERE usecase_id={int(usecase_id)} ORDER BY id DESC LIMIT 1)
    ORDER BY s.selected_order;
    """

def w_generate_executive_strategy(usecase_id: int, title: str) -> str:
    safe_title = title.replace("'", "''")
    return f"""
    CREATE TABLE IF NOT EXISTS Next_ExecutiveStrategy (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      usecase_id INTEGER NOT NULL,
      strategy_title TEXT,
      transformation_vision TEXT,
      strategic_priorities TEXT,
      roadmap_summary TEXT,
      investment_summary TEXT,
      risk_summary TEXT,
      outcome_summary TEXT,
      created_on DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    INSERT INTO Next_ExecutiveStrategy (
      usecase_id, strategy_title, transformation_vision,
      strategic_priorities, roadmap_summary, investment_summary,
      risk_summary, outcome_summary
    )
    VALUES (
      {int(usecase_id)},
      '{safe_title}',
      'Establish a secure, automated platform aligned to the selected use case.',
      'Top clusters and investments drive the highest enterprise impact.',
      'Phased roadmap derived from cluster priorities and capability dependencies.',
      'Portfolio derived from benefit-per-cost optimization.',
      'Key risks: dependency readiness, data quality, and change adoption.',
      'Expected outcomes: improved delivery speed, resilience, and security posture.'
    );
    """

def q_latest_executive_strategy(usecase_id: int) -> str:
    return f"SELECT * FROM Next_ExecutiveStrategy WHERE usecase_id={int(usecase_id)} ORDER BY id DESC LIMIT 1;"
