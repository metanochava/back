from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from saude.models.medico import Medico

from django_resaas.hr.models.specialty import Specialty
from django_resaas.hr.models.employee_specialty import EmployeeSpecialty


class MedicoSerializer(BaseSerializer):

    especialidade = serializers.PrimaryKeyRelatedField(
        queryset=Specialty.objects.all(),
        many=True,
        required=False,
        write_only=True
    )

    class Meta:
        model = Medico
        fields = "__all__"

    def create(self, validated_data):

        especialidades = validated_data.pop(
            "especialidade",
            []
        )

        medico = super().create(
            validated_data
        )

        for specialty in especialidades:

            EmployeeSpecialty.objects.get_or_create(
                employee=medico.employee,
                specialty=specialty
            )

        return medico

    def update(self, instance, validated_data):

        especialidades = validated_data.pop(
            "especialidade",
            None
        )

        medico = super().update(
            instance,
            validated_data
        )

        if especialidades is not None:

            EmployeeSpecialty.objects.filter(
                employee=medico.employee
            ).delete()

            EmployeeSpecialty.objects.bulk_create([
                EmployeeSpecialty(
                    employee=medico.employee,
                    specialty=specialty
                )
                for specialty in especialidades
            ])

        return medico

    def to_representation(self, instance):

        data = super().to_representation(instance)

        employee_specialties = (
            EmployeeSpecialty.objects
            .filter(
                employee=instance.employee
            )
            .select_related("specialty")
        )

        data["especialidade"] = [
            {
                "id": str(item.specialty.id),
                "label": item.specialty.title,
                "value": str(item.specialty.id),
            }
            for item in employee_specialties
            if item.specialty
        ]

        return data