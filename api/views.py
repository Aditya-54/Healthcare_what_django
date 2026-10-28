from django.contrib.auth import authenticate, get_user_model
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Doctor, Patient, PatientDoctorMapping
from .permissions import IsOwner
from .serializers import (
    DoctorSerializer,
    LoginSerializer,
    MappingReadSerializer,
    MappingSerializer,
    PatientSerializer,
    RegisterSerializer,
)

User = get_user_model()


# --- Auth ---

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"id": user.id, "email": user.email, "name": user.name},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()
        password = serializer.validated_data["password"]
        user = authenticate(request, username=email, password=password)

        if user is None:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )


# --- Patients ---

class PatientListCreateView(generics.ListCreateAPIView):
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users only ever see their own patients
        return Patient.objects.filter(created_by=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class PatientDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Patient.objects.filter(created_by=self.request.user)

    def get_object(self):
        try:
            obj = self.get_queryset().get(pk=self.kwargs["pk"])
        except Patient.DoesNotExist:
            raise NotFound("Patient not found.")
        self.check_object_permissions(self.request, obj)
        return obj

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Doctors ---

class DoctorListCreateView(generics.ListCreateAPIView):
    serializer_class = DoctorSerializer
    permission_classes = [IsAuthenticated]
    queryset = Doctor.objects.all().order_by("name")


class DoctorDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DoctorSerializer
    permission_classes = [IsAuthenticated]
    queryset = Doctor.objects.all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Patient-Doctor Mappings ---

class MappingListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Only mappings for patients owned by this user
        mappings = (
            PatientDoctorMapping.objects
            .filter(patient__created_by=request.user)
            .select_related("patient", "doctor")
            .order_by("-assigned_at")
        )
        serializer = MappingReadSerializer(mappings, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = MappingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        patient = serializer.validated_data["patient"]
        # Verify the patient belongs to the requesting user
        if patient.created_by != request.user:
            raise PermissionDenied("You do not have permission to assign doctors to this patient.")

        try:
            mapping = serializer.save()
        except Exception:
            raise ValidationError("This doctor is already assigned to this patient.")

        return Response(MappingReadSerializer(mapping).data, status=status.HTTP_201_CREATED)


class MappingByPatientView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):
        # Confirm patient exists and belongs to this user
        try:
            patient = Patient.objects.get(pk=patient_id, created_by=request.user)
        except Patient.DoesNotExist:
            raise NotFound("Patient not found.")

        mappings = (
            PatientDoctorMapping.objects
            .filter(patient=patient)
            .select_related("patient", "doctor")
        )
        serializer = MappingReadSerializer(mappings, many=True)
        return Response(serializer.data)


class MappingDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            mapping = (
                PatientDoctorMapping.objects
                .select_related("patient")
                .get(pk=pk, patient__created_by=request.user)
            )
        except PatientDoctorMapping.DoesNotExist:
            raise NotFound("Mapping not found.")

        mapping.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
