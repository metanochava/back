from rest_framework import serializers
from django_resaas.models.user import User
from django_resaas.data.user.serializers.user import UserSerializer 


from django_resaas.core.base.serializers import BaseSerializer
from saude.models.diagnostico import Diagnostico


class DiagnosticoSerializer(BaseSerializer):

    paciente = serializers.SerializerMethodField()

    medico = serializers.SerializerMethodField()

    class Meta:
        model = Diagnostico
        fields = "__all__"

    def get_paciente(self, obj):

        person = obj.consulta.paciente.person

        return {
            "id": person.id,
            "name": person.full_name
        }

    def get_medico(self, obj):

        medico = getattr(obj.consulta, "medico", None)

        if not medico:
            return None

        user = getattr(medico.employee.person, "user", None)

        profile = None

        if user:
            profile = UserSerializer(
                User.objects.get(id=user.id),
                context={
                    **self.context,
                    "include_fields": ["profile"]
                }
            ).data["profile"]

        return {
            "name": medico.employee.person.full_name,
            "profile": profile
        }