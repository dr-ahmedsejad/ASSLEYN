from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.academics.views import (
    AcademicYearViewSet,
    CurriculumViewSet,
    EnrollmentViewSet,
    SectionViewSet,
    SemesterViewSet,
    SubjectViewSet,
    TeachingAssignmentViewSet,
)

router = DefaultRouter()
router.register("years", AcademicYearViewSet, basename="year")
router.register("semesters", SemesterViewSet, basename="semester")
router.register("sections", SectionViewSet, basename="section")
router.register("subjects", SubjectViewSet, basename="subject")
router.register("curricula", CurriculumViewSet, basename="curriculum")
router.register("enrollments", EnrollmentViewSet, basename="enrollment")
router.register("assignments", TeachingAssignmentViewSet, basename="assignment")

urlpatterns = [path("", include(router.urls))]
