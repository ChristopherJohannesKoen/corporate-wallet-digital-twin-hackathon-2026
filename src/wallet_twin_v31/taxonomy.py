"""Governed V3.1 taxonomies and policy matrices.

Every enumeration and matrix in this module is a *governed artifact*: it is
versioned, registered in MLflow and cannot be changed by a model or by the LLM.
The problem-solution matrix, the stakeholder responsibility matrix and the
solution lead-time policy are the three artifacts a bank product/credit forum
would have to approve before V3.1 could leave the demonstration boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Mapping, Sequence, Tuple

TAXONOMY_VERSION = "v31-business-taxonomy-3.1.1"
RESPONSIBILITY_MATRIX_VERSION = "v31-stakeholder-responsibility-3.1.1"
PROBLEM_SOLUTION_MATRIX_VERSION = "v31-problem-solution-matrix-3.1.1"


# ---------------------------------------------------------------------------
# Stakeholder roles
# ---------------------------------------------------------------------------
class StakeholderRole(str, Enum):
    """Role personas only.  No named individual is resolved in the demo."""

    CEO_BOARD = "CEO_BOARD"
    CFO = "CFO"
    TREASURER = "TREASURER"
    COO = "COO"
    PROCUREMENT = "PROCUREMENT"
    FINANCE_OPERATIONS = "FINANCE_OPERATIONS"
    RISK_LEGAL = "RISK_LEGAL"
    SUSTAINABILITY = "SUSTAINABILITY"
    CORPORATE_DEVELOPMENT = "CORPORATE_DEVELOPMENT"
    CIO_TECHNOLOGY = "CIO_TECHNOLOGY"


# ---------------------------------------------------------------------------
# Business problems
# ---------------------------------------------------------------------------
class BusinessProblem(str, Enum):
    WORKING_CAPITAL_PRESSURE = "WORKING_CAPITAL_PRESSURE"
    FX_EXPOSURE = "FX_EXPOSURE"
    INTEREST_RATE_EXPOSURE = "INTEREST_RATE_EXPOSURE"
    COMMODITY_EXPOSURE = "COMMODITY_EXPOSURE"
    LIQUIDITY_FRAGMENTATION = "LIQUIDITY_FRAGMENTATION"
    REFINANCING_CLIFF = "REFINANCING_CLIFF"
    NEW_FUNDING_REQUIREMENT = "NEW_FUNDING_REQUIREMENT"
    PAYMENTS_INEFFICIENCY = "PAYMENTS_INEFFICIENCY"
    COLLECTIONS_INEFFICIENCY = "COLLECTIONS_INEFFICIENCY"
    SUPPLY_CHAIN_RISK = "SUPPLY_CHAIN_RISK"
    PROJECT_MOBILISATION = "PROJECT_MOBILISATION"
    GUARANTEE_OR_COLLATERAL_REQUIREMENT = "GUARANTEE_OR_COLLATERAL_REQUIREMENT"
    TREASURY_CENTRALISATION = "TREASURY_CENTRALISATION"
    CAPITAL_STRUCTURE_EVENT = "CAPITAL_STRUCTURE_EVENT"
    MA_OR_STRATEGIC_EVENT = "MA_OR_STRATEGIC_EVENT"
    ESG_TRANSITION_FUNDING = "ESG_TRANSITION_FUNDING"
    WALLET_LEAKAGE = "WALLET_LEAKAGE"
    OPERATIONAL_RESILIENCE = "OPERATIONAL_RESILIENCE"


PROBLEM_LABELS: Mapping[BusinessProblem, str] = {
    BusinessProblem.WORKING_CAPITAL_PRESSURE: "Working-capital pressure",
    BusinessProblem.FX_EXPOSURE: "FX exposure",
    BusinessProblem.INTEREST_RATE_EXPOSURE: "Interest-rate exposure",
    BusinessProblem.COMMODITY_EXPOSURE: "Commodity exposure",
    BusinessProblem.LIQUIDITY_FRAGMENTATION: "Liquidity fragmentation",
    BusinessProblem.REFINANCING_CLIFF: "Refinancing cliff",
    BusinessProblem.NEW_FUNDING_REQUIREMENT: "New funding requirement",
    BusinessProblem.PAYMENTS_INEFFICIENCY: "Payments inefficiency",
    BusinessProblem.COLLECTIONS_INEFFICIENCY: "Collections inefficiency",
    BusinessProblem.SUPPLY_CHAIN_RISK: "Supply-chain risk",
    BusinessProblem.PROJECT_MOBILISATION: "Project mobilisation",
    BusinessProblem.GUARANTEE_OR_COLLATERAL_REQUIREMENT: "Guarantee or collateral requirement",
    BusinessProblem.TREASURY_CENTRALISATION: "Treasury centralisation",
    BusinessProblem.CAPITAL_STRUCTURE_EVENT: "Capital-structure event",
    BusinessProblem.MA_OR_STRATEGIC_EVENT: "M&A or strategic event",
    BusinessProblem.ESG_TRANSITION_FUNDING: "ESG-transition funding",
    BusinessProblem.WALLET_LEAKAGE: "Wallet leakage",
    BusinessProblem.OPERATIONAL_RESILIENCE: "Operational resilience",
}


# ---------------------------------------------------------------------------
# Banking solutions
# ---------------------------------------------------------------------------
class BankingSolution(str, Enum):
    COLLECTIONS = "COLLECTIONS"
    PAYMENTS = "PAYMENTS"
    LIQUIDITY_CASH_MANAGEMENT = "LIQUIDITY_CASH_MANAGEMENT"
    CROSS_BORDER_FX = "CROSS_BORDER_FX"
    TRADE_FINANCE = "TRADE_FINANCE"
    SUPPLY_CHAIN_FINANCE = "SUPPLY_CHAIN_FINANCE"
    GUARANTEES_AND_LC = "GUARANTEES_AND_LC"
    WORKING_CAPITAL_REVOLVING = "WORKING_CAPITAL_REVOLVING"
    TERM_AND_SYNDICATED_LENDING = "TERM_AND_SYNDICATED_LENDING"
    DEBT_CAPITAL_MARKETS = "DEBT_CAPITAL_MARKETS"
    PROJECT_FINANCE = "PROJECT_FINANCE"
    INTEREST_RATE_RISK_MANAGEMENT = "INTEREST_RATE_RISK_MANAGEMENT"
    COMMODITY_RISK_MANAGEMENT = "COMMODITY_RISK_MANAGEMENT"
    ESCROW_AND_AGENCY = "ESCROW_AND_AGENCY"
    SUSTAINABLE_FINANCE = "SUSTAINABLE_FINANCE"
    MA_AND_STRATEGIC_ADVISORY = "MA_AND_STRATEGIC_ADVISORY"


SOLUTION_LABELS: Mapping[BankingSolution, str] = {
    BankingSolution.COLLECTIONS: "Collections",
    BankingSolution.PAYMENTS: "Payments",
    BankingSolution.LIQUIDITY_CASH_MANAGEMENT: "Liquidity and cash management",
    BankingSolution.CROSS_BORDER_FX: "Cross-border FX",
    BankingSolution.TRADE_FINANCE: "Trade finance",
    BankingSolution.SUPPLY_CHAIN_FINANCE: "Supply-chain finance",
    BankingSolution.GUARANTEES_AND_LC: "Guarantees and letters of credit",
    BankingSolution.WORKING_CAPITAL_REVOLVING: "Working-capital/revolving credit",
    BankingSolution.TERM_AND_SYNDICATED_LENDING: "Term and syndicated lending",
    BankingSolution.DEBT_CAPITAL_MARKETS: "Debt capital markets",
    BankingSolution.PROJECT_FINANCE: "Project finance",
    BankingSolution.INTEREST_RATE_RISK_MANAGEMENT: "Interest-rate risk management",
    BankingSolution.COMMODITY_RISK_MANAGEMENT: "Commodity risk management",
    BankingSolution.ESCROW_AND_AGENCY: "Escrow and agency services",
    BankingSolution.SUSTAINABLE_FINANCE: "Sustainable finance",
    BankingSolution.MA_AND_STRATEGIC_ADVISORY: "M&A and strategic advisory",
}

SOLUTION_CATALOGUE: Tuple[BankingSolution, ...] = tuple(BankingSolution)


class SolutionFamily(str, Enum):
    TRANSACTION_BANKING = "TRANSACTION_BANKING"
    RISK_MANAGEMENT = "RISK_MANAGEMENT"
    TRADE_AND_WORKING_CAPITAL = "TRADE_AND_WORKING_CAPITAL"
    LENDING = "LENDING"
    CAPITAL_MARKETS = "CAPITAL_MARKETS"
    ADVISORY_AND_AGENCY = "ADVISORY_AND_AGENCY"


SOLUTION_FAMILY: Mapping[BankingSolution, SolutionFamily] = {
    BankingSolution.COLLECTIONS: SolutionFamily.TRANSACTION_BANKING,
    BankingSolution.PAYMENTS: SolutionFamily.TRANSACTION_BANKING,
    BankingSolution.LIQUIDITY_CASH_MANAGEMENT: SolutionFamily.TRANSACTION_BANKING,
    BankingSolution.CROSS_BORDER_FX: SolutionFamily.RISK_MANAGEMENT,
    BankingSolution.INTEREST_RATE_RISK_MANAGEMENT: SolutionFamily.RISK_MANAGEMENT,
    BankingSolution.COMMODITY_RISK_MANAGEMENT: SolutionFamily.RISK_MANAGEMENT,
    BankingSolution.TRADE_FINANCE: SolutionFamily.TRADE_AND_WORKING_CAPITAL,
    BankingSolution.SUPPLY_CHAIN_FINANCE: SolutionFamily.TRADE_AND_WORKING_CAPITAL,
    BankingSolution.GUARANTEES_AND_LC: SolutionFamily.TRADE_AND_WORKING_CAPITAL,
    BankingSolution.WORKING_CAPITAL_REVOLVING: SolutionFamily.LENDING,
    BankingSolution.TERM_AND_SYNDICATED_LENDING: SolutionFamily.LENDING,
    BankingSolution.PROJECT_FINANCE: SolutionFamily.LENDING,
    BankingSolution.DEBT_CAPITAL_MARKETS: SolutionFamily.CAPITAL_MARKETS,
    BankingSolution.SUSTAINABLE_FINANCE: SolutionFamily.CAPITAL_MARKETS,
    BankingSolution.ESCROW_AND_AGENCY: SolutionFamily.ADVISORY_AND_AGENCY,
    BankingSolution.MA_AND_STRATEGIC_ADVISORY: SolutionFamily.ADVISORY_AND_AGENCY,
}

#: The principal modelled quantity per solution.  V3.1 quantifies every
#: solution, but the *quantity* differs: notional exposure is not a wallet and
#: a mandate fee is not a transaction margin.
PRINCIPAL_QUANTITY: Mapping[BankingSolution, str] = {
    BankingSolution.COLLECTIONS: "TRANSACTION_WALLET",
    BankingSolution.PAYMENTS: "TRANSACTION_WALLET",
    BankingSolution.LIQUIDITY_CASH_MANAGEMENT: "CASH_WALLET",
    BankingSolution.CROSS_BORDER_FX: "EXPOSURE_NOTIONAL",
    BankingSolution.INTEREST_RATE_RISK_MANAGEMENT: "EXPOSURE_NOTIONAL",
    BankingSolution.COMMODITY_RISK_MANAGEMENT: "EXPOSURE_NOTIONAL",
    BankingSolution.TRADE_FINANCE: "ELIGIBLE_FLOW",
    BankingSolution.SUPPLY_CHAIN_FINANCE: "ELIGIBLE_FLOW",
    BankingSolution.GUARANTEES_AND_LC: "CONTINGENT_EXPOSURE",
    BankingSolution.WORKING_CAPITAL_REVOLVING: "FACILITY_SIZE",
    BankingSolution.TERM_AND_SYNDICATED_LENDING: "FACILITY_SIZE",
    BankingSolution.DEBT_CAPITAL_MARKETS: "FINANCING_REQUIREMENT",
    BankingSolution.PROJECT_FINANCE: "PROJECT_FUNDING_REQUIREMENT",
    BankingSolution.ESCROW_AND_AGENCY: "EVENT_LINKED_FLOW",
    BankingSolution.SUSTAINABLE_FINANCE: "ELIGIBLE_CAPEX",
    BankingSolution.MA_AND_STRATEGIC_ADVISORY: "TRANSACTION_SIZE",
}

#: The five V3.0 products keep their posterior wallet engines; the mapping lets
#: V3.1 reuse the frozen bounds instead of re-deriving them.
LEGACY_PRODUCT_SOLUTION: Mapping[str, BankingSolution] = {
    "Collections": BankingSolution.COLLECTIONS,
    "Payments": BankingSolution.PAYMENTS,
    "Liquidity": BankingSolution.LIQUIDITY_CASH_MANAGEMENT,
    "Cross-border FX": BankingSolution.CROSS_BORDER_FX,
    "Trade finance": BankingSolution.TRADE_FINANCE,
}
SOLUTION_LEGACY_PRODUCT: Mapping[BankingSolution, str] = {
    value: key for key, value in LEGACY_PRODUCT_SOLUTION.items()
}


# ---------------------------------------------------------------------------
# Business Model Twin domains
# ---------------------------------------------------------------------------
class BusinessTwinDomain(str, Enum):
    REVENUE_ENGINE = "REVENUE_ENGINE"
    COST_ENGINE = "COST_ENGINE"
    WORKING_CAPITAL_CYCLE = "WORKING_CAPITAL_CYCLE"
    FUNDING_STRUCTURE = "FUNDING_STRUCTURE"
    LIQUIDITY_AND_BUFFER = "LIQUIDITY_AND_BUFFER"
    OPERATING_MODEL = "OPERATING_MODEL"
    GEOGRAPHIC_EXPOSURE = "GEOGRAPHIC_EXPOSURE"
    CURRENCY_AND_COMMODITY_EXPOSURE = "CURRENCY_AND_COMMODITY_EXPOSURE"
    PROJECTS_SUBSIDIARIES_SPVS = "PROJECTS_SUBSIDIARIES_SPVS"
    STAKEHOLDER_RESPONSIBILITY = "STAKEHOLDER_RESPONSIBILITY"
    BUSINESS_AND_FINANCIAL_RISKS = "BUSINESS_AND_FINANCIAL_RISKS"
    STRATEGY_ACTIONS_AND_ESG = "STRATEGY_ACTIONS_AND_ESG"


BUSINESS_TWIN_DOMAINS: Tuple[BusinessTwinDomain, ...] = tuple(BusinessTwinDomain)

DOMAIN_LABELS: Mapping[BusinessTwinDomain, str] = {
    BusinessTwinDomain.REVENUE_ENGINE: "Revenue engine",
    BusinessTwinDomain.COST_ENGINE: "Cost engine",
    BusinessTwinDomain.WORKING_CAPITAL_CYCLE: "Working-capital cycle",
    BusinessTwinDomain.FUNDING_STRUCTURE: "Funding structure",
    BusinessTwinDomain.LIQUIDITY_AND_BUFFER: "Liquidity and cash buffer",
    BusinessTwinDomain.OPERATING_MODEL: "Operating model",
    BusinessTwinDomain.GEOGRAPHIC_EXPOSURE: "Geographic exposure",
    BusinessTwinDomain.CURRENCY_AND_COMMODITY_EXPOSURE: "Currency and commodity exposure",
    BusinessTwinDomain.PROJECTS_SUBSIDIARIES_SPVS: "Projects, subsidiaries and SPVs",
    BusinessTwinDomain.STAKEHOLDER_RESPONSIBILITY: "Stakeholder responsibility model",
    BusinessTwinDomain.BUSINESS_AND_FINANCIAL_RISKS: "Business and financial risks",
    BusinessTwinDomain.STRATEGY_ACTIONS_AND_ESG: "Strategy, corporate actions and ESG activity",
}


class ComponentStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class BusinessClaimKind(str, Enum):
    MONEY = "MONEY"
    RATIO = "RATIO"
    COUNT = "COUNT"
    DATE_OR_MATURITY = "DATE_OR_MATURITY"
    CATEGORICAL = "CATEGORICAL"
    TEXTUAL = "TEXTUAL"
    STRUCTURE_RELATIONSHIP = "STRUCTURE_RELATIONSHIP"
    EVENT_OR_PROJECT = "EVENT_OR_PROJECT"


# ---------------------------------------------------------------------------
# Feasibility, value and routing
# ---------------------------------------------------------------------------
class FeasibilityGate(str, Enum):
    PRODUCT_CAPABILITY = "PRODUCT_CAPABILITY"
    CREDIT_AND_RISK = "CREDIT_AND_RISK"
    COMPLIANCE_AND_CONDUCT = "COMPLIANCE_AND_CONDUCT"
    LEGAL_AND_JURISDICTION = "LEGAL_AND_JURISDICTION"
    OPERATIONS_AND_ONBOARDING = "OPERATIONS_AND_ONBOARDING"
    TECHNOLOGY_AND_INTEGRATION = "TECHNOLOGY_AND_INTEGRATION"


FEASIBILITY_GATES: Tuple[FeasibilityGate, ...] = tuple(FeasibilityGate)


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_REQUIRED = "NOT_REQUIRED"


class ClientValueStatus(str, Enum):
    MONETISED = "MONETISED"
    PROXY = "PROXY"
    QUALITATIVE = "QUALITATIVE"
    UNAVAILABLE = "UNAVAILABLE"


class FundingRoute(str, Enum):
    BANK_DEBT = "BANK_DEBT"
    BOND_DCM = "BOND_DCM"
    EQUITY = "EQUITY"
    PROJECT_FINANCE = "PROJECT_FINANCE"
    INTERNAL_CASH = "INTERNAL_CASH"
    HYBRID_OTHER = "HYBRID_OTHER"


FUNDING_ROUTES: Tuple[FundingRoute, ...] = tuple(FundingRoute)


class ConversationAction(str, Enum):
    """What the RM is actually being asked to do."""

    PRODUCT_PROPOSAL = "PRODUCT_PROPOSAL"
    DISCOVERY = "DISCOVERY"
    EVIDENCE_ACQUISITION = "EVIDENCE_ACQUISITION"
    VALIDATION = "VALIDATION"


class EligibilityDecision(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    DISCOVERY_ONLY = "DISCOVERY_ONLY"
    BLOCKED = "BLOCKED"


# ---------------------------------------------------------------------------
# Problem-solution matrix
# ---------------------------------------------------------------------------
class MappingStrength(str, Enum):
    PRIMARY = "PRIMARY"
    SUPPORTING = "SUPPORTING"
    INCOMPATIBLE = "INCOMPATIBLE"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"


@dataclass(frozen=True)
class ProblemSolutionMapping:
    problem: BusinessProblem
    solution: BankingSolution
    strength: MappingStrength
    prerequisites: Tuple[str, ...] = ()
    permitted_roles: Tuple[StakeholderRole, ...] = ()
    lead_time_days: int = 30

    @property
    def selectable(self) -> bool:
        return self.strength is not MappingStrength.INCOMPATIBLE


#: Solution-specific preparation lead times, in days, used by the engagement
#: window calculation.  These are governed policy, not model outputs.
SOLUTION_LEAD_TIME_DAYS: Mapping[BankingSolution, int] = {
    BankingSolution.COLLECTIONS: 30,
    BankingSolution.PAYMENTS: 30,
    BankingSolution.LIQUIDITY_CASH_MANAGEMENT: 45,
    BankingSolution.CROSS_BORDER_FX: 21,
    BankingSolution.TRADE_FINANCE: 45,
    BankingSolution.SUPPLY_CHAIN_FINANCE: 75,
    BankingSolution.GUARANTEES_AND_LC: 35,
    BankingSolution.WORKING_CAPITAL_REVOLVING: 60,
    BankingSolution.TERM_AND_SYNDICATED_LENDING: 90,
    BankingSolution.DEBT_CAPITAL_MARKETS: 120,
    BankingSolution.PROJECT_FINANCE: 150,
    BankingSolution.INTEREST_RATE_RISK_MANAGEMENT: 30,
    BankingSolution.COMMODITY_RISK_MANAGEMENT: 30,
    BankingSolution.ESCROW_AND_AGENCY: 40,
    BankingSolution.SUSTAINABLE_FINANCE: 110,
    BankingSolution.MA_AND_STRATEGIC_ADVISORY: 120,
}

_P = MappingStrength.PRIMARY
_S = MappingStrength.SUPPORTING
_R = MappingStrength.REQUIRES_CONFIRMATION

#: problem -> {solution: (strength, prerequisites)}.  Every pair not listed is
#: INCOMPATIBLE by default and can never be bundled for that problem.
_MATRIX_SPEC: Dict[
    BusinessProblem, Dict[BankingSolution, Tuple[MappingStrength, Tuple[str, ...]]]
] = {
    BusinessProblem.WORKING_CAPITAL_PRESSURE: {
        BankingSolution.WORKING_CAPITAL_REVOLVING: (_P, ("approved credit limit",)),
        BankingSolution.SUPPLY_CHAIN_FINANCE: (_P, ("supplier onboarding capability",)),
        BankingSolution.TRADE_FINANCE: (_S, ()),
        BankingSolution.COLLECTIONS: (_S, ()),
        BankingSolution.LIQUIDITY_CASH_MANAGEMENT: (_S, ()),
        BankingSolution.PAYMENTS: (_S, ()),
    },
    BusinessProblem.FX_EXPOSURE: {
        BankingSolution.CROSS_BORDER_FX: (_P, ()),
        BankingSolution.INTEREST_RATE_RISK_MANAGEMENT: (_S, ()),
        BankingSolution.LIQUIDITY_CASH_MANAGEMENT: (_S, ()),
        BankingSolution.TRADE_FINANCE: (_S, ()),
        BankingSolution.PAYMENTS: (_S, ()),
    },
    BusinessProblem.INTEREST_RATE_EXPOSURE: {
        BankingSolution.INTEREST_RATE_RISK_MANAGEMENT: (_P, ("ISDA/CSA in place",)),
        BankingSolution.TERM_AND_SYNDICATED_LENDING: (_S, ()),
        BankingSolution.DEBT_CAPITAL_MARKETS: (_S, ()),
        BankingSolution.WORKING_CAPITAL_REVOLVING: (_S, ()),
    },
    BusinessProblem.COMMODITY_EXPOSURE: {
        BankingSolution.COMMODITY_RISK_MANAGEMENT: (_P, ("ISDA/CSA in place",)),
        BankingSolution.CROSS_BORDER_FX: (_S, ()),
        BankingSolution.TRADE_FINANCE: (_S, ()),
        BankingSolution.WORKING_CAPITAL_REVOLVING: (_S, ()),
    },
    BusinessProblem.LIQUIDITY_FRAGMENTATION: {
        BankingSolution.LIQUIDITY_CASH_MANAGEMENT: (_P, ("multi-entity mandate",)),
        BankingSolution.PAYMENTS: (_S, ()),
        BankingSolution.COLLECTIONS: (_S, ()),
        BankingSolution.CROSS_BORDER_FX: (_S, ()),
    },
    BusinessProblem.REFINANCING_CLIFF: {
        BankingSolution.TERM_AND_SYNDICATED_LENDING: (_P, ("approved credit limit",)),
        BankingSolution.DEBT_CAPITAL_MARKETS: (_P, ("issuer rating or programme",)),
        BankingSolution.INTEREST_RATE_RISK_MANAGEMENT: (_S, ()),
        BankingSolution.WORKING_CAPITAL_REVOLVING: (_S, ()),
        BankingSolution.SUSTAINABLE_FINANCE: (_R, ("eligible use-of-proceeds",)),
    },
    BusinessProblem.NEW_FUNDING_REQUIREMENT: {
        BankingSolution.TERM_AND_SYNDICATED_LENDING: (_P, ("approved credit limit",)),
        BankingSolution.DEBT_CAPITAL_MARKETS: (_P, ("issuer rating or programme",)),
        BankingSolution.PROJECT_FINANCE: (_R, ("ring-fenced project cash flows",)),
        BankingSolution.WORKING_CAPITAL_REVOLVING: (_S, ()),
        BankingSolution.SUSTAINABLE_FINANCE: (_R, ("eligible use-of-proceeds",)),
        BankingSolution.INTEREST_RATE_RISK_MANAGEMENT: (_S, ()),
    },
    BusinessProblem.PAYMENTS_INEFFICIENCY: {
        BankingSolution.PAYMENTS: (_P, ("ERP/host-to-host capability",)),
        BankingSolution.LIQUIDITY_CASH_MANAGEMENT: (_S, ()),
        BankingSolution.CROSS_BORDER_FX: (_S, ()),
        BankingSolution.COLLECTIONS: (_S, ()),
    },
    BusinessProblem.COLLECTIONS_INEFFICIENCY: {
        BankingSolution.COLLECTIONS: (_P, ("reconciliation/ERP integration",)),
        BankingSolution.LIQUIDITY_CASH_MANAGEMENT: (_S, ()),
        BankingSolution.SUPPLY_CHAIN_FINANCE: (_S, ()),
        BankingSolution.PAYMENTS: (_S, ()),
    },
    BusinessProblem.SUPPLY_CHAIN_RISK: {
        BankingSolution.SUPPLY_CHAIN_FINANCE: (_P, ("supplier onboarding capability",)),
        BankingSolution.TRADE_FINANCE: (_P, ()),
        BankingSolution.GUARANTEES_AND_LC: (_S, ()),
        BankingSolution.COMMODITY_RISK_MANAGEMENT: (_S, ()),
        BankingSolution.CROSS_BORDER_FX: (_S, ()),
    },
    BusinessProblem.PROJECT_MOBILISATION: {
        BankingSolution.PROJECT_FINANCE: (_P, ("ring-fenced project cash flows",)),
        BankingSolution.GUARANTEES_AND_LC: (_P, ()),
        BankingSolution.ESCROW_AND_AGENCY: (_S, ()),
        BankingSolution.TERM_AND_SYNDICATED_LENDING: (_S, ()),
        BankingSolution.SUSTAINABLE_FINANCE: (_R, ("eligible use-of-proceeds",)),
        BankingSolution.CROSS_BORDER_FX: (_S, ()),
    },
    BusinessProblem.GUARANTEE_OR_COLLATERAL_REQUIREMENT: {
        BankingSolution.GUARANTEES_AND_LC: (_P, ("approved contingent limit",)),
        BankingSolution.TRADE_FINANCE: (_S, ()),
        BankingSolution.ESCROW_AND_AGENCY: (_S, ()),
        BankingSolution.WORKING_CAPITAL_REVOLVING: (_S, ()),
    },
    BusinessProblem.TREASURY_CENTRALISATION: {
        BankingSolution.LIQUIDITY_CASH_MANAGEMENT: (_P, ("multi-entity mandate",)),
        BankingSolution.PAYMENTS: (_P, ("ERP/host-to-host capability",)),
        BankingSolution.CROSS_BORDER_FX: (_S, ()),
        BankingSolution.COLLECTIONS: (_S, ()),
        BankingSolution.INTEREST_RATE_RISK_MANAGEMENT: (_S, ()),
    },
    BusinessProblem.CAPITAL_STRUCTURE_EVENT: {
        BankingSolution.DEBT_CAPITAL_MARKETS: (_P, ("issuer rating or programme",)),
        BankingSolution.TERM_AND_SYNDICATED_LENDING: (_P, ()),
        BankingSolution.MA_AND_STRATEGIC_ADVISORY: (_R, ("mandate conflict clearance",)),
        BankingSolution.INTEREST_RATE_RISK_MANAGEMENT: (_S, ()),
        BankingSolution.ESCROW_AND_AGENCY: (_S, ()),
    },
    BusinessProblem.MA_OR_STRATEGIC_EVENT: {
        BankingSolution.MA_AND_STRATEGIC_ADVISORY: (_P, ("mandate conflict clearance",)),
        BankingSolution.ESCROW_AND_AGENCY: (_P, ()),
        BankingSolution.TERM_AND_SYNDICATED_LENDING: (_S, ()),
        BankingSolution.DEBT_CAPITAL_MARKETS: (_S, ()),
        BankingSolution.CROSS_BORDER_FX: (_S, ()),
    },
    BusinessProblem.ESG_TRANSITION_FUNDING: {
        BankingSolution.SUSTAINABLE_FINANCE: (_P, ("eligible use-of-proceeds",)),
        BankingSolution.PROJECT_FINANCE: (_R, ("ring-fenced project cash flows",)),
        BankingSolution.TERM_AND_SYNDICATED_LENDING: (_S, ()),
        BankingSolution.DEBT_CAPITAL_MARKETS: (_S, ()),
    },
    BusinessProblem.WALLET_LEAKAGE: {
        BankingSolution.PAYMENTS: (_P, ()),
        BankingSolution.COLLECTIONS: (_P, ()),
        BankingSolution.CROSS_BORDER_FX: (_P, ()),
        BankingSolution.TRADE_FINANCE: (_S, ()),
        BankingSolution.LIQUIDITY_CASH_MANAGEMENT: (_S, ()),
    },
    BusinessProblem.OPERATIONAL_RESILIENCE: {
        BankingSolution.PAYMENTS: (_P, ("ERP/host-to-host capability",)),
        BankingSolution.LIQUIDITY_CASH_MANAGEMENT: (_P, ()),
        BankingSolution.COLLECTIONS: (_S, ()),
        BankingSolution.GUARANTEES_AND_LC: (_S, ()),
        BankingSolution.ESCROW_AND_AGENCY: (_R, ("agency mandate capability",)),
    },
}


# ---------------------------------------------------------------------------
# Stakeholder responsibility matrix
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ResponsibilityRule:
    problem: BusinessProblem
    primary: StakeholderRole
    secondary: Tuple[StakeholderRole, ...]
    primary_weight: float
    rationale: str
    requires_rm_confirmation: bool = True


_RESPONSIBILITY: Tuple[ResponsibilityRule, ...] = (
    ResponsibilityRule(
        BusinessProblem.WORKING_CAPITAL_PRESSURE,
        StakeholderRole.CFO,
        (StakeholderRole.TREASURER, StakeholderRole.PROCUREMENT),
        0.55,
        "Cash-conversion outcomes sit with the CFO; execution shares with treasury and procurement.",
    ),
    ResponsibilityRule(
        BusinessProblem.FX_EXPOSURE,
        StakeholderRole.TREASURER,
        (StakeholderRole.CFO,),
        0.70,
        "Hedging policy and execution authority are treasury-owned in a centralised model.",
    ),
    ResponsibilityRule(
        BusinessProblem.INTEREST_RATE_EXPOSURE,
        StakeholderRole.TREASURER,
        (StakeholderRole.CFO,),
        0.68,
        "Rate risk on the debt stack is managed by treasury within a board-approved policy.",
    ),
    ResponsibilityRule(
        BusinessProblem.COMMODITY_EXPOSURE,
        StakeholderRole.TREASURER,
        (StakeholderRole.COO, StakeholderRole.PROCUREMENT),
        0.50,
        "Commodity hedging spans treasury policy and operating/procurement volume ownership.",
    ),
    ResponsibilityRule(
        BusinessProblem.LIQUIDITY_FRAGMENTATION,
        StakeholderRole.TREASURER,
        (StakeholderRole.FINANCE_OPERATIONS, StakeholderRole.CFO),
        0.62,
        "Account structure and cash concentration are treasury design decisions.",
    ),
    ResponsibilityRule(
        BusinessProblem.REFINANCING_CLIFF,
        StakeholderRole.TREASURER,
        (StakeholderRole.CFO, StakeholderRole.CEO_BOARD),
        0.55,
        "Refinancing execution is treasury-led with CFO and board approval of the structure.",
    ),
    ResponsibilityRule(
        BusinessProblem.NEW_FUNDING_REQUIREMENT,
        StakeholderRole.CFO,
        (StakeholderRole.TREASURER, StakeholderRole.CEO_BOARD),
        0.52,
        "New funding requires CFO sponsorship; treasury structures and the board approves.",
    ),
    ResponsibilityRule(
        BusinessProblem.PAYMENTS_INEFFICIENCY,
        StakeholderRole.FINANCE_OPERATIONS,
        (StakeholderRole.TREASURER, StakeholderRole.CIO_TECHNOLOGY),
        0.50,
        "Payment run economics are owned by finance operations with treasury and IT dependencies.",
    ),
    ResponsibilityRule(
        BusinessProblem.COLLECTIONS_INEFFICIENCY,
        StakeholderRole.FINANCE_OPERATIONS,
        (StakeholderRole.CFO, StakeholderRole.CIO_TECHNOLOGY),
        0.52,
        "Receivables reconciliation and DSO sit with finance operations under CFO targets.",
    ),
    ResponsibilityRule(
        BusinessProblem.SUPPLY_CHAIN_RISK,
        StakeholderRole.PROCUREMENT,
        (StakeholderRole.COO, StakeholderRole.CFO),
        0.48,
        "Supplier concentration and terms are procurement-owned with operational and cash impact.",
    ),
    ResponsibilityRule(
        BusinessProblem.PROJECT_MOBILISATION,
        StakeholderRole.COO,
        (StakeholderRole.CFO, StakeholderRole.TREASURER),
        0.45,
        "Project delivery is operations-led; funding and guarantees require finance and treasury.",
    ),
    ResponsibilityRule(
        BusinessProblem.GUARANTEE_OR_COLLATERAL_REQUIREMENT,
        StakeholderRole.TREASURER,
        (StakeholderRole.RISK_LEGAL, StakeholderRole.COO),
        0.50,
        "Contingent instruments are issued by treasury against legal and operational requirements.",
    ),
    ResponsibilityRule(
        BusinessProblem.TREASURY_CENTRALISATION,
        StakeholderRole.TREASURER,
        (StakeholderRole.CFO, StakeholderRole.CIO_TECHNOLOGY),
        0.65,
        "Target treasury operating model is a treasury design owned with CFO sponsorship.",
    ),
    ResponsibilityRule(
        BusinessProblem.CAPITAL_STRUCTURE_EVENT,
        StakeholderRole.CFO,
        (StakeholderRole.CEO_BOARD, StakeholderRole.TREASURER),
        0.50,
        "Capital-structure changes are CFO-proposed and board-approved.",
    ),
    ResponsibilityRule(
        BusinessProblem.MA_OR_STRATEGIC_EVENT,
        StakeholderRole.CORPORATE_DEVELOPMENT,
        (StakeholderRole.CEO_BOARD, StakeholderRole.CFO),
        0.48,
        "Transaction origination sits with corporate development under CEO/board mandate.",
    ),
    ResponsibilityRule(
        BusinessProblem.ESG_TRANSITION_FUNDING,
        StakeholderRole.SUSTAINABILITY,
        (StakeholderRole.CFO, StakeholderRole.TREASURER),
        0.42,
        "Transition targets are sustainability-owned; the funding instrument is finance-owned.",
    ),
    ResponsibilityRule(
        BusinessProblem.WALLET_LEAKAGE,
        StakeholderRole.TREASURER,
        (StakeholderRole.FINANCE_OPERATIONS, StakeholderRole.CFO),
        0.55,
        "Bank-panel allocation decisions are treasury decisions.",
    ),
    ResponsibilityRule(
        BusinessProblem.OPERATIONAL_RESILIENCE,
        StakeholderRole.COO,
        (StakeholderRole.CIO_TECHNOLOGY, StakeholderRole.RISK_LEGAL),
        0.45,
        "Continuity of payment and cash operations is an operations and technology accountability.",
    ),
)

RESPONSIBILITY_MATRIX: Mapping[BusinessProblem, ResponsibilityRule] = {
    rule.problem: rule for rule in _RESPONSIBILITY
}

#: Roles that may be approached about a solution at all.  Used to intersect the
#: problem-derived role with the solution bundle so that, for example, a DCM
#: conversation is never routed to procurement.
SOLUTION_PERMITTED_ROLES: Mapping[BankingSolution, Tuple[StakeholderRole, ...]] = {
    BankingSolution.COLLECTIONS: (
        StakeholderRole.FINANCE_OPERATIONS,
        StakeholderRole.TREASURER,
        StakeholderRole.CFO,
    ),
    BankingSolution.PAYMENTS: (
        StakeholderRole.FINANCE_OPERATIONS,
        StakeholderRole.TREASURER,
        StakeholderRole.CFO,
        StakeholderRole.CIO_TECHNOLOGY,
        StakeholderRole.COO,
    ),
    BankingSolution.LIQUIDITY_CASH_MANAGEMENT: (
        StakeholderRole.TREASURER,
        StakeholderRole.CFO,
        StakeholderRole.FINANCE_OPERATIONS,
        StakeholderRole.COO,
    ),
    BankingSolution.CROSS_BORDER_FX: (
        StakeholderRole.TREASURER,
        StakeholderRole.CFO,
        StakeholderRole.FINANCE_OPERATIONS,
        StakeholderRole.PROCUREMENT,
        StakeholderRole.COO,
        StakeholderRole.CORPORATE_DEVELOPMENT,
    ),
    BankingSolution.TRADE_FINANCE: (
        StakeholderRole.TREASURER,
        StakeholderRole.CFO,
        StakeholderRole.PROCUREMENT,
        StakeholderRole.COO,
    ),
    BankingSolution.SUPPLY_CHAIN_FINANCE: (
        StakeholderRole.PROCUREMENT,
        StakeholderRole.CFO,
        StakeholderRole.TREASURER,
        StakeholderRole.FINANCE_OPERATIONS,
        StakeholderRole.COO,
    ),
    BankingSolution.GUARANTEES_AND_LC: (
        StakeholderRole.TREASURER,
        StakeholderRole.RISK_LEGAL,
        StakeholderRole.COO,
        StakeholderRole.CFO,
    ),
    BankingSolution.WORKING_CAPITAL_REVOLVING: (
        StakeholderRole.CFO,
        StakeholderRole.TREASURER,
        StakeholderRole.PROCUREMENT,
    ),
    BankingSolution.TERM_AND_SYNDICATED_LENDING: (
        StakeholderRole.CFO,
        StakeholderRole.TREASURER,
        StakeholderRole.CEO_BOARD,
        StakeholderRole.COO,
        StakeholderRole.SUSTAINABILITY,
    ),
    BankingSolution.DEBT_CAPITAL_MARKETS: (
        StakeholderRole.CFO,
        StakeholderRole.TREASURER,
        StakeholderRole.CEO_BOARD,
        StakeholderRole.SUSTAINABILITY,
    ),
    BankingSolution.PROJECT_FINANCE: (
        StakeholderRole.CFO,
        StakeholderRole.TREASURER,
        StakeholderRole.COO,
        StakeholderRole.CORPORATE_DEVELOPMENT,
        StakeholderRole.SUSTAINABILITY,
    ),
    BankingSolution.INTEREST_RATE_RISK_MANAGEMENT: (
        StakeholderRole.TREASURER,
        StakeholderRole.CFO,
        StakeholderRole.CEO_BOARD,
    ),
    BankingSolution.COMMODITY_RISK_MANAGEMENT: (
        StakeholderRole.TREASURER,
        StakeholderRole.COO,
        StakeholderRole.PROCUREMENT,
        StakeholderRole.CFO,
    ),
    BankingSolution.ESCROW_AND_AGENCY: (
        StakeholderRole.RISK_LEGAL,
        StakeholderRole.CORPORATE_DEVELOPMENT,
        StakeholderRole.TREASURER,
        StakeholderRole.CFO,
        StakeholderRole.COO,
    ),
    BankingSolution.SUSTAINABLE_FINANCE: (
        StakeholderRole.SUSTAINABILITY,
        StakeholderRole.CFO,
        StakeholderRole.TREASURER,
        StakeholderRole.CEO_BOARD,
        StakeholderRole.COO,
    ),
    BankingSolution.MA_AND_STRATEGIC_ADVISORY: (
        StakeholderRole.CORPORATE_DEVELOPMENT,
        StakeholderRole.CEO_BOARD,
        StakeholderRole.CFO,
    ),
}


def _build_matrix() -> Mapping[
    Tuple[BusinessProblem, BankingSolution], ProblemSolutionMapping
]:
    matrix: Dict[Tuple[BusinessProblem, BankingSolution], ProblemSolutionMapping] = {}
    for problem in BusinessProblem:
        spec = _MATRIX_SPEC.get(problem, {})
        for solution in BankingSolution:
            strength, prerequisites = spec.get(
                solution, (MappingStrength.INCOMPATIBLE, ())
            )
            matrix[(problem, solution)] = ProblemSolutionMapping(
                problem=problem,
                solution=solution,
                strength=strength,
                prerequisites=prerequisites,
                permitted_roles=SOLUTION_PERMITTED_ROLES[solution],
                lead_time_days=SOLUTION_LEAD_TIME_DAYS[solution],
            )
    return matrix


PROBLEM_SOLUTION_MATRIX: Mapping[
    Tuple[BusinessProblem, BankingSolution], ProblemSolutionMapping
] = _build_matrix()


def mapping_for(
    problem: BusinessProblem, solution: BankingSolution
) -> ProblemSolutionMapping:
    return PROBLEM_SOLUTION_MATRIX[(problem, solution)]


def primary_solutions(problem: BusinessProblem) -> Tuple[BankingSolution, ...]:
    return tuple(
        solution
        for solution in BankingSolution
        if mapping_for(problem, solution).strength is MappingStrength.PRIMARY
    )


def supporting_solutions(problem: BusinessProblem) -> Tuple[BankingSolution, ...]:
    return tuple(
        solution
        for solution in BankingSolution
        if mapping_for(problem, solution).strength
        in (MappingStrength.SUPPORTING, MappingStrength.REQUIRES_CONFIRMATION)
    )


#: Bundles that may not be proposed together in the same conversation.
MUTUALLY_EXCLUSIVE_SOLUTIONS: Tuple[frozenset, ...] = (
    frozenset({BankingSolution.DEBT_CAPITAL_MARKETS, BankingSolution.PROJECT_FINANCE}),
    frozenset(
        {BankingSolution.SUPPLY_CHAIN_FINANCE, BankingSolution.TRADE_FINANCE}
    ),
)


def mutually_exclusive(solutions: Sequence[BankingSolution]) -> bool:
    chosen = set(solutions)
    return any(pair <= chosen for pair in MUTUALLY_EXCLUSIVE_SOLUTIONS)


@dataclass(frozen=True)
class TaxonomyRegistration:
    """Registration record published to MLflow alongside the taxonomy."""

    artifact: str
    version: str
    owner: str
    approval_required_before_production: bool = True
    notes: str = ""
    blocking_gates: Tuple[str, ...] = field(default_factory=tuple)


REGISTERED_TAXONOMIES: Tuple[TaxonomyRegistration, ...] = (
    TaxonomyRegistration(
        "business-domain-taxonomy",
        TAXONOMY_VERSION,
        "Corporate Banking Analytics",
        notes="Twelve Business Twin domains, eighteen problems, sixteen solutions.",
        blocking_gates=("bank business-domain ontology approval",),
    ),
    TaxonomyRegistration(
        "stakeholder-responsibility-matrix",
        RESPONSIBILITY_MATRIX_VERSION,
        "Client Coverage",
        notes="Role personas only; CRM person resolution is out of scope for the demo.",
        blocking_gates=("coverage policy approval", "CRM entitlement design"),
    ),
    TaxonomyRegistration(
        "problem-solution-matrix",
        PROBLEM_SOLUTION_MATRIX_VERSION,
        "Product Management",
        notes="PRIMARY/SUPPORTING/REQUIRES_CONFIRMATION/INCOMPATIBLE with prerequisites and lead times.",
        blocking_gates=("product capability confirmation", "credit policy approval"),
    ),
)
