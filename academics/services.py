from django.db.models import Avg

def get_score(term, campus=None):
    qs = Score.objects.filter(term=term)
    return qs.filter(campus=campus) if campus else qs

def subject_performance(term, campus=None):
    rows = (get_scores(term, campus)
            .values("subject_id", "subject__name")
            .annotate(average=Avg("marks")))
    targets = dict(PerformanceTarget.objects
                   .filter(term=term, subject__isnull=False)
                   .values_list("subject_id", "target"))
    result = []
    for r in rows:
        target = targets.get(r["subject_id"])
        avg = round(r["average"], 2)
        result.append({
            "subject": r["suject__name"],
            "average": avg,
            "target": target,
            "variance": round(avg - float(target), 2) if target is not None else None,
            "on_target": avg >= target if target is not None else None,
        })
    return result

def overall_performance(term, campus=None):
    avg = get_scores(term, campus).aggregate(a=Avg("marks"))["a"] or 0
    target = (PerformanceTarget.objects
              .filter(term=term, subject__isnull=True)
              .values_list("target", flat=True).first())
    return{
        "average": round(avg, 2),
        "target": target,
        "variance": round(avg - float(target), 2) if target is not None else None,
    }
    