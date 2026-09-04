"""
Policy Simulator REST API Routes — RecoverAI Milestone 16
Provides endpoints for running read-only policy simulations, viewing simulation results, and comparing baseline vs. optimized policies.
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.models.policy_simulation import PolicySimulation
from backend.services.policy_simulator import PolicySimulator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulator", tags=["Policy Simulator"])

@router.post("/run")
def run_policy_simulation(
    limit: int = Query(default=500, ge=1, le=5000, description="Max transaction count for simulation"),
    batch_run_id: Optional[str] = Query(default=None, description="Optional batch run correlation ID"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Run side-by-side policy simulation comparing baseline vs RecoverAI optimized policy.
    Read-only guarantee: zero Razorpay API calls, zero live case mutations.
    """
    try:
        res = PolicySimulator.run_simulation(db, batch_run_id=batch_run_id, limit=limit)
        return res
    except Exception as e:
        logger.error(f"Error running policy simulation: {e}")
        raise HTTPException(status_code=500, detail=f"Policy simulation failed: {str(e)}")

@router.get("/results")
def list_simulation_results(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    List historical PolicySimulation run records.
    """
    sims = db.query(PolicySimulation).order_by(PolicySimulation.created_at.desc()).limit(limit).all()
    
    results = []
    for s in sims:
        results.append({
            "id": s.id,
            "batch_run_id": s.batch_run_id,
            "policy_name": s.policy_name,
            "total_transactions": s.total_transactions,
            "revenue_at_risk_paise": s.revenue_at_risk_paise,
            "revenue_at_risk_rupees": round(s.revenue_at_risk_paise / 100.0, 2),
            "eligible_count": s.eligible_count,
            "eligible_revenue_paise": s.eligible_revenue_paise,
            "projected_recovered_paise": s.projected_recovered_paise,
            "projected_recovered_rupees": round(s.projected_recovered_paise / 100.0, 2),
            "projected_recovery_rate": s.projected_recovery_rate,
            "actions_projected": s.actions_projected,
            "policy_blocks_projected": s.policy_blocks_projected,
            "escalations_projected": s.escalations_projected,
            "contacts_projected": s.contacts_projected,
            "simulation_mode": s.simulation_mode,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })

    return {
        "count": len(results),
        "results": results,
    }

@router.get("/compare")
def compare_policy_simulations(
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Side-by-side comparison of latest baseline vs RecoverAI optimized policy runs.
    """
    return PolicySimulator.run_simulation(db, limit=limit)
