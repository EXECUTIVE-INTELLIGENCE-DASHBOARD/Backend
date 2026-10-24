from django.db.models import Avg

from .models import AssessmentResult, PerformanceTarget


def get_results(term, campus=None, kind=None):
    """Assessment results for a term, optionally for one campus or one kind of assessment."""
    qs = AssessmentResult.objects.filter(assessment__term=term)
    if campus:
        qs = qs.filter(assessment__school__campus=campus)  # "kibuli", "buwaate" or "annex"
    if kind:
        qs = qs.filter(assessment__kind=kind)  # e.g. "end_of_term"
    return qs


def _compare(avg, target):
    """The gap between average and target, and whether the target was met."""
    if avg is None or target is None:
        return {"variance": None, "on_target": None}
    return {"variance": round(avg - target, 2), "on_target": avg >= target}


def subject_performance(term, campus=None, kind=None):
    rows = (
        get_results(term, campus, kind)
        .values(
            "assessment__subject_id",
            "assessment__subject__name",
            "assessment__subject__level",
        )
        .annotate(average=Avg("mark"))
        .order_by("assessment__subject__level", "assessment__subject__name")
    )
    targets = {
        subject_id: float(target)
        for subject_id, target in PerformanceTarget.objects.filter(
            term=term, subject__isnull=False
        ).values_list("subject_id", "target")
    }
    result = []
    for r in rows:
        avg = round(float(r["average"]), 2)
        target = targets.get(r["assessment__subject_id"])
        result.append({
            "subject": r["assessment__subject__name"],
            "level": r["assessment__subject__level"],
            "average": avg,
            "target": target,
            **_compare(avg, target),
        })
    return result


def overall_performance(term, campus=None, kind=None):
    avg = get_results(term, campus, kind).aggregate(a=Avg("mark"))["a"]
    avg = round(float(avg), 2) if avg is not None else None
    target = (
        PerformanceTarget.objects.filter(term=term, subject__isnull=True)
        .values_list("target", flat=True)
        .first()
    )
    target = float(target) if target is not None else None
    return {"average": avg, "target": target, **_compare(avg, target)}