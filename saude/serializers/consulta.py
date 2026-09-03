from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.consulta import Consulta
from rest_framework import serializers
from django_resaas.engine.data.user.serializers.user import UserSerializer
from django_resaas.engine.models.user import User

class ConsultaSerializer(BaseSerializer):
    
    class Meta:
        model = Consulta
        fields = "__all__"
    

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

   