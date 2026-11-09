# hr/views/employee_specialty.py

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.employee_specialty import EmployeeSpecialty
from hr.serializers.employee_specialty import EmployeeSpecialtySerializer


@registerView('employeespecialtys', module='hr')
class EmployeeSpecialtyAPIView(BaseAPIView):
    queryset = EmployeeSpecialty.objects.all()
    serializer_class = EmployeeSpecialtySerializer

    def create(self, request, *args, **kwargs):
        # A specialty removed from the employee is soft-deleted and still holds
        # the (employee, specialty) pair of unique_together: adding it again
        # restores that row (this Entity's only) instead of failing.
        employee_id = request.data.get("employee")
        specialty_id = request.data.get("specialty")
        if employee_id and specialty_id:
            removed = (
                EmployeeSpecialty.deleted_objects
                .filter(employee_id=employee_id, specialty_id=specialty_id, entity_id=request.entity_id)
                .first()
            )
            if removed is not None:
                with transaction.atomic():
                    removed.restore(user=request.user)
                return Response(self.get_serializer(removed).data, status=status.HTTP_201_CREATED)
        return super().create(request, *args, **kwargs)
