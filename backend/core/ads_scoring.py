"""
Ads health scoring — pure logic, no API calls.

Turns raw campaign/insight data into:
  - ads_score (0-100)
  - findings (what's wrong / what's good)
  - recommended_actions (specific, actionable, goal-aware)

The same shape is used by the real-data endpoint and the mock endpoint,
so the frontend renders one component for both.
"""

# --- Thresholds (sane defaults for SMB Meta ads) ---
GOOD_CTR = 1.5        # %
GOOD_CPM = 15.0       # $
GOOD_CPC = 0.75       # $
GOOD_COST_PER_LEAD = 8.0  # $
GOOD_FREQUENCY = 2.5  # 2.5+ means the same person saw the ad repeatedly


def score_ads(snapshot: dict, campaigns: list[dict] | None = None, goal: str = "sales") -> dict:
    """Returns {ads_score, findings, recommended_actions, summary}."""
    campaigns = campaigns or []
    findings: list[str] = []
    actions: list[str] = []
    score = 100

    active = [c for c in campaigns if c.get("effective_status") == "ACTIVE"]
    paused = [c for c in campaigns if c.get("effective_status") in ("PAUSED", "CAMPAIGN_PAUSED")]
    deleted = [c for c in campaigns if c.get("effective_status") in ("DELETED", "ARCHIVED", "CAMPAIGN_PAUSED", "ARCHIVED")]

    # 1. Campaign health
    if not campaigns:
        findings.append("No campaigns found in this ad account.")
        actions.append("Create your first campaign, or connect the ad account that holds your ads.")
        score -= 50
    else:
        if not active:
            findings.append("No campaigns are currently active — all are paused or ended.")
            actions.append("Review paused campaigns and turn on at least one, or duplicate a winning one.")
            score -= 35
        elif len(active) < len(campaigns) * 0.5:
            findings.append(f"Only {len(active)} of {len(campaigns)} campaigns are active.")
            actions.append("Audit paused campaigns: relaunch winners, archive underperformers.")
            score -= 10

    # 2. Volume signals
    if snapshot.get("impressions", 0) == 0:
        findings.append("No impressions in the last 30 days — ads aren't being shown.")
        actions.append("Check campaign delivery, budget, and audience size (may be too narrow).")
        score -= 30
    elif snapshot.get("impressions", 0) < 10_000:
        findings.append(f"Low volume: only {snapshot['impressions']:,} impressions in 30 days.")
        actions.append("Raise budget or widen targeting to gather more data.")
        score -= 10

    # 3. Engagement / relevance
    ctr = snapshot.get("ctr", 0)
    if ctr < 0.5:
        findings.append(f"Low CTR ({ctr}%) — creative or offer isn't resonating.")
        actions.append("Refresh ad creative: new hook, clearer offer, or different image/video.")
        score -= 15
    elif ctr >= GOOD_CTR:
        findings.append(f"Strong CTR ({ctr}%) — creative is connecting with the audience.")

    frequency = snapshot.get("frequency", 0)
    if frequency >= GOOD_FREQUENCY:
        findings.append(f"High frequency ({frequency}) — the same people are seeing the ad repeatedly.")
        actions.append("Expand audience or refresh creative to avoid ad fatigue.")
        score -= 10

    # 4. Cost efficiency
    if snapshot.get("spend", 0) > 0:
        cpm = snapshot.get("cpm", 0)
        if cpm > GOOD_CPM * 1.5:
            findings.append(f"Expensive reach: CPM ${cpm:.2f}.")
            actions.append("Narrow broad targeting, test interest stacks, or switch placements.")
            score -= 8
        cpc = snapshot.get("cpc", 0)
        if cpc > GOOD_CPC * 2:
            findings.append(f"High CPC (${cpc:.2f}) — paying a lot per click.")
            actions.append("Improve relevance score with tighter ad-to-audience match.")
            score -= 8

    # 5. Goal-specific: results & cost per result
    goal = (goal or "sales").lower()
    if "lead" in goal:
        leads = snapshot.get("leads", 0)
        if leads == 0:
            findings.append("Goal is leads, but no leads were recorded in 30 days.")
            actions.append("Verify the Meta Pixel / lead form fires, and that the objective is set to 'Leads'.")
            score -= 25
        else:
            cpl = snapshot.get("cost_per_lead", 0)
            if cpl and cpl > GOOD_COST_PER_LEAD:
                findings.append(f"Cost per lead ${cpl:.2f} is above the ${GOOD_COST_PER_LEAD:.0f} target.")
                actions.append("Improve landing page conversion or narrow audience to cheaper leads.")
                score -= 10
            else:
                findings.append(f"Healthy cost per lead (${cpl:.2f}) — {leads} leads this month.")
    elif "sale" in goal or "purchase" in goal or "revenue" in goal:
        purchases = snapshot.get("purchases", 0)
        if purchases == 0:
            findings.append("Goal is sales, but no purchases were recorded in 30 days.")
            actions.append("Check Pixel purchase event, conversion tracking, and landing page checkout flow.")
            score -= 25
        else:
            if snapshot.get("spend", 0) > 0:
                roas = snapshot["spend"] / purchases
                if roas > 1:
                    findings.append(f"Each sale costs ~${roas:.2f} — watch profitability against margins.")
                else:
                    findings.append(f"~${roas:.2f} per purchase — solid if margins allow.")
    else:
        # Generic engagement goal
        if snapshot.get("clicks", 0) == 0 and snapshot.get("impressions", 0) > 0:
            findings.append("Impressions but zero clicks — the ad isn't prompting action.")
            actions.append("Tighten the CTA and make the offer unmissable in the first line.")
            score -= 15

    # 6. Positive reinforcement
    if not findings:
        findings.append("Ads look healthy: active campaigns, good CTR, reasonable costs.")

    if not actions:
        actions.append("Keep scaling budget on the best campaign and test one new creative per week.")

    # Clamp & label
    score = max(0, min(100, score))
    if score >= 80:
        label = "healthy"
    elif score >= 50:
        label = "needs attention"
    else:
        label = "critical"

    return {
        "ads_score": score,
        "label": label,
        "findings": findings[:6],
        "recommended_actions": actions[:6],
        "summary": snapshot,
    }


def mock_ads_report() -> dict:
    """Demo data so the Ads Health panel always renders, even before Meta is connected."""
    snapshot = {
        "spend": 412.35,
        "impressions": 48310,
        "clicks": 1124,
        "ctr": 2.33,
        "cpc": 0.37,
        "cpm": 8.53,
        "reach": 15060,
        "frequency": 3.21,
        "leads": 57,
        "purchases": 12,
        "cost_per_lead": 7.23,
    }
    campaigns = [
        {"name": "Summer Launch — Prospecting", "effective_status": "ACTIVE"},
        {"name": "Retargeting — Cart Abandoners", "effective_status": "ACTIVE"},
        {"name": "Old Catalog (ended)", "effective_status": "ARCHIVED"},
    ]
    result = score_ads(snapshot, campaigns, goal="sales")
    result["is_mock"] = True
    result["note"] = "Sample data — connect a Meta ad account for your real numbers."
    return result
