# hr/views/course.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.course import Course
from hr.serializers.course import CourseSerializer


@registerView('courses', module='hr')
class CourseAPIView(BaseAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
