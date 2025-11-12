from django.urls import path
from .views import GradeSingleView, GradeBatchView, DemoGradeView

urlpatterns = [
    path("grade/single/", GradeSingleView.as_view(), name="grade-single"),
    path("grade/batch/", GradeBatchView.as_view(), name="grade-batch"),
    path('demo-grade/', DemoGradeView.as_view(), name='demo-grade'),
]
