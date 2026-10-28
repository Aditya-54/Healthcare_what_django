from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RegisterView,
    LoginView,
    PatientListCreateView,
    PatientDetailView,
    DoctorListCreateView,
    DoctorDetailView,
    MappingListCreateView,
    MappingByPatientView,
    MappingDeleteView,
)

urlpatterns = [
    # Auth
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Patients
    path("patients/", PatientListCreateView.as_view(), name="patient-list-create"),
    path("patients/<int:pk>/", PatientDetailView.as_view(), name="patient-detail"),

    # Doctors
    path("doctors/", DoctorListCreateView.as_view(), name="doctor-list-create"),
    path("doctors/<int:pk>/", DoctorDetailView.as_view(), name="doctor-detail"),

    # Mappings
    path("mappings/", MappingListCreateView.as_view(), name="mapping-list-create"),
    path("mappings/<int:patient_id>/", MappingByPatientView.as_view(), name="mapping-by-patient"),
    path("mappings/delete/<int:pk>/", MappingDeleteView.as_view(), name="mapping-delete"),
]
