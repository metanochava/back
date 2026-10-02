from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from saude.models.medico import Medico

from django_resaas.saas.core.utils.translate import Translate

from hr.models.specialty import Specialty
from hr.models.employee_specialty import EmployeeSpecialty


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

    def validate_especialidade(self, specialties):
        # a specialty of another Entity must never be linked (tenant isolation)
        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None)
        if entity_id and any(str(s.entity_id) != str(entity_id) for s in specialties):
            raise serializers.ValidationError(Translate.tdc(request, "Invalid specialty."))
        return specialties

    def create(self, validated_data):

        especialidades = validated_data.pop(
            "especialidade",
            []
        )

        medico = super().create(
            validated_data
        )

        self._set_specialties(medico, especialidades)

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
            self._set_specialties(medico, especialidades, replace=True)

        return medico

    def _set_specialties(self, medico, specialties, replace=False):
        """EmployeeSpecialty rows in the doctor's own tenant (BaseModel requires
        an explicit entity and branch - without them saving a doctor with
        specialties failed with a 500)."""
        request = self.context.get("request")
        actor = getattr(request, "user", None)
        wanted = {specialty.id: specialty for specialty in specialties}

        if replace:
            EmployeeSpecialty.objects.filter(employee=medico.employee).exclude(
                specialty_id__in=wanted
            ).delete()

        for specialty in wanted.values():
            EmployeeSpecialty.objects.get_or_create(
                employee=medico.employee,
                specialty=specialty,
                defaults={
                    "entity_id": medico.entity_id,
                    "branch_id": medico.branch_id,
                    "created_by": actor,
                    "updated_by": actor,
                },
            )

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