from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.pedidoexamemedico import PedidoExameMedico
from rest_framework import serializers
from django_resaas.saas.data.user.serializers.user import UserSerializer
from django_resaas.saas.models.user import User



class PedidoExameMedicoSerializer(BaseSerializer):
    
    class Meta:
        model = PedidoExameMedico
        fields = "__all__"
        # set by the server on create (exam_request_service): the patient
        # comes from the current Entity, the origin from the entry flow
        read_only_fields = ["paciente", "origin"]
    

    # =========================
    # 👤 EMPLOYEE + PROFILE
    # =========================
    medico = serializers.SerializerMethodField()
    def get_medico(self, obj):

        # a direct (exam-only) request has no consultation, so no doctor
        if not obj.consulta_id or not obj.consulta.employee:
            return None

        # 🔥 user/profile
        user = getattr(obj.consulta.employee.person, 'user', None)

        if user:
            
            user = User.objects.get(id=user.id)
            user_data = UserSerializer( user,
                context={  **self.context, "include_fields": ["profile"] }
            ).data


            return {'name' : obj.consulta.employee.person.full_name, 'profile': user_data['profile']}

        else:
            return None

   