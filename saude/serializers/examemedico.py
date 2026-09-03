from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.examemedico import ExameMedico
from rest_framework import serializers

class ExameMedicoSerializer(BaseSerializer):
    
    class Meta:
        model = ExameMedico
        fields = "__all__"
    

    # =========================
    # 👤 EMPLOYEE + PROFILE
    # =========================
    # medico = serializers.SerializerMethodField()
    # def get_medico(self, obj):

    #     if not obj.consulta.employee:
    #         return None

    #     # 🔥 user/profile
    #     user = getattr(obj.consulta.employee.person, 'user', None)

    #     if user:
            
    #         user = User.objects.get(id=user.id)
    #         user_data = UserSerializer( user,
    #             context={  **self.context, "include_fields": ["profile"] }
    #         ).data


    #         return {'name' : obj.consulta.employee.person.full_name, 'profile': user_data['profile']}

    #     else:
    #         return None

   