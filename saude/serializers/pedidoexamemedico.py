from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.pedidoexamemedico import PedidoExameMedico
from rest_framework import serializers
from django_resaas.engine.data.user.serializers.user import UserSerializer
from django_resaas.engine.models.user import User



class PedidoExameMedicoSerializer(BaseSerializer):
    
    class Meta:
        model = PedidoExameMedico
        fields = "__all__"
    

    # =========================
    # 👤 EMPLOYEE + PROFILE
    # =========================
    medico = serializers.SerializerMethodField()
    def get_medico(self, obj):

        if not obj.consulta.employee:
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

   