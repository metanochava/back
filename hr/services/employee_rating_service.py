"""Employee ratings (hr.EmployeeRating): rating, averages, moderation.

Generic HR - the module that owns the rated service (saude: a completed
appointment) checks who may rate and calls rate() with its source. hr never
imports that module.

Scopes of an average (the viewer chooses):

    entity  the employee's ratings in its own Entity;
    global  the same Person's ratings in every Entity whose employee row
            shares them (Employee.share_ratings_globally), plus this one's.

Comments are always only this Entity's and only the approved ones; the rater
is never returned.
"""
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from django_resaas.saas.core.exceptions import ResaasAPIException

from hr.models.employee_rating import EmployeeRating, EmployeeRatingCommentStatus as Status

SCOPES = ("entity", "global")


def parse_scope(value):
    return value if value in SCOPES else "entity"


def _scope_filter(employee, scope):
    if scope == "global":
        return Q(employee_id=employee.id) | Q(
            employee__person_id=employee.person_id,
            employee__share_ratings_globally=True,
            employee__deleted_at__isnull=True,
        )
    return Q(employee_id=employee.id, entity_id=employee.entity_id)


def _average(value):
    return round(float(value), 1) if value is not None else None


def summary(employee, scope="entity", comments=5, pending=False):
    """{scope, average, count, distribution: {"1".."5"}, comments: [...],
    pending: [...] (only with pending=True - for whoever moderates)}."""
    scope = parse_scope(scope)
    ratings = EmployeeRating.objects.filter(_scope_filter(employee, scope))
    totals = ratings.aggregate(average=Avg("stars"), count=Count("id"))
    distribution = {str(n): 0 for n in range(1, 6)}
    for row in ratings.values("stars").annotate(n=Count("id")):
        distribution[str(row["stars"])] = row["n"]

    own = EmployeeRating.objects.filter(employee_id=employee.id, entity_id=employee.entity_id).exclude(comment__isnull=True).exclude(comment="")
    data = {
        "scope": scope,
        "average": _average(totals["average"]),
        "count": totals["count"],
        "distribution": distribution,
        "comments": [_comment(r) for r in own.filter(comment_status=Status.APPROVED)[:comments]],
    }
    if pending:
        data["pending"] = [_comment(r) for r in own.filter(comment_status=Status.PENDING)[:50]]
    return data


def averages(employee_ids):
    """{employee_id: {average, count}} of this Entity, in one query (lists)."""
    rows = (
        EmployeeRating.objects.filter(employee_id__in=list(employee_ids))
        .values("employee_id").annotate(average=Avg("stars"), count=Count("id"))
    )
    return {str(r["employee_id"]): {"average": _average(r["average"]), "count": r["count"]} for r in rows}


def _comment(rating):
    return {
        "id": str(rating.id),
        "stars": rating.stars,
        "comment": rating.comment,
        "date": rating.created_at.date().isoformat(),
        "status": rating.comment_status,
    }


def rate(*, employee, stars, comment, source_type, source_id, rated_by=None, branch_id=None):
    """One rating per source (409 already_rated on a repeat). The rating
    belongs to the employee's Entity; branch: the service's, else the
    employee's."""
    try:
        stars = int(stars)
    except (TypeError, ValueError):
        stars = 0
    if not 1 <= stars <= 5:
        raise ResaasAPIException("Choose from 1 to 5 stars.", code="invalid_stars", details={"stars": ["Choose from 1 to 5 stars."]})

    comment = (comment or "").strip()[:2000] or None
    rating = EmployeeRating(
        employee=employee,
        entity_id=employee.entity_id,
        branch_id=branch_id or employee.branch_id,
        rated_by=rated_by,
        stars=stars,
        comment=comment,
        # without a comment there is nothing to moderate
        comment_status=Status.PENDING if comment else Status.APPROVED,
        source_type=source_type,
        source_id=source_id,
    )
    if EmployeeRating.all_objects.filter(source_type=source_type, source_id=source_id).exists():
        raise already_rated()
    try:
        with transaction.atomic():
            rating.save()
    except IntegrityError:   # a concurrent request rated the same source
        raise already_rated()
    return rating


def already_rated():
    return ResaasAPIException("This has already been rated.", code="already_rated", status_code=409)


def moderate(rating, status, user):
    """Approve or reject the comment of a rating (the stars always count)."""
    if status not in (Status.APPROVED, Status.REJECTED):
        raise ResaasAPIException("Choose approve or reject.", code="invalid_status", details={"status": ["Choose approve or reject."]})
    rating.comment_status = status
    rating.moderated_at = timezone.now()
    rating.moderated_by = user if getattr(user, "is_authenticated", False) else None
    rating.save(update_fields=["comment_status", "moderated_at", "moderated_by", "updated_at"])
    return rating


def public_profile(employee, scope="entity"):
    """What anyone may see of an employee: name, bio, languages, specialties
    and the ratings (never HR data, contacts, signature or stamp)."""
    from hr.models.employee_specialty import EmployeeSpecialty

    return {
        "id": str(employee.id),
        "name": employee.person.full_name,
        "bio": (employee.public_bio or "").strip(),
        "languages": (employee.public_languages or "").strip(),
        "specialties": [
            {"id": str(item.specialty_id), "title": item.specialty.title}
            for item in EmployeeSpecialty.objects.filter(employee_id=employee.id, specialty__isnull=False)
            .select_related("specialty").order_by("specialty__title")
        ],
        "rating": summary(employee, scope),
    }
