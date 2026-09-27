from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.consulta import Consulta
from rest_framework import serializers
from django_resaas.saas.data.user.serializers.user import UserSerializer
from django_resaas.saas.models.user import User

class ConsultaSerializer(BaseSerializer):
    
    class Meta:
        model = Consulta
        fields = "__all__"
        # the professional signed in (ConsultaAPIView.perform_create)
        read_only_fields = ["employee"]
    

    # =========================
    # 👤 EMPLOYEE + PROFILE
    # =========================
    medico = serializers.SerializerMethodField()
    def get_medico(self, obj):

        if not obj.employee:
            return None

        # 🔥 user/profile
        user = getattr(obj.employee.person, 'user', None)

        if user:
            
            user = User.objects.get(id=user.id)
            user_data = UserSerializer( user,
                context={  **self.context, "include_fields": ["profile"] }
            ).data


            return {'name' : obj.employee.person.full_name, 'profile': user_data['profile']}

        else:
            return None

   