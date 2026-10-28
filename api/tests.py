from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Doctor, Patient, PatientDoctorMapping

User = get_user_model()


def make_user(email="alice@example.com", name="Alice", password="TestPass123!"):
    return User.objects.create_user(email=email, name=name, password=password)


def auth_header(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class AuthTests(APITestCase):
    def test_register_success(self):
        resp = self.client.post("/api/auth/register/", {
            "email": "bob@example.com", "name": "Bob", "password": "TestPass123!",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["email"], "bob@example.com")

    def test_register_duplicate_email(self):
        make_user("dup@example.com")
        resp = self.client.post("/api/auth/register/", {
            "email": "DUP@example.com", "name": "Dup", "password": "TestPass123!",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_success(self):
        make_user("carol@example.com", password="TestPass123!")
        resp = self.client.post("/api/auth/login/", {
            "email": "carol@example.com", "password": "TestPass123!",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_login_wrong_password(self):
        make_user("dave@example.com", password="TestPass123!")
        resp = self.client.post("/api/auth/login/", {
            "email": "dave@example.com", "password": "wrong",
        })
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_access_denied(self):
        resp = self.client.get("/api/patients/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class PatientTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.other = make_user("other@example.com", name="Other")
        self.headers = auth_header(self.user)
        self.other_headers = auth_header(self.other)

    def _make_patient(self, headers=None):
        return self.client.post("/api/patients/", {
            "first_name": "Jane", "last_name": "Doe",
            "date_of_birth": "1990-05-15", "gender": "Female",
        }, **( headers or self.headers))

    def test_create_patient(self):
        resp = self._make_patient()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["first_name"], "Jane")

    def test_list_patients_scoped_to_user(self):
        self._make_patient()
        self._make_patient(self.other_headers)
        resp = self.client.get("/api/patients/", **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", resp.data)
        self.assertEqual(len(results), 1)

    def test_cross_user_patient_access_denied(self):
        resp = self._make_patient()
        patient_id = resp.data["id"]
        resp2 = self.client.get(f"/api/patients/{patient_id}/", **self.other_headers)
        self.assertEqual(resp2.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_patient(self):
        resp = self._make_patient()
        pid = resp.data["id"]
        resp2 = self.client.put(f"/api/patients/{pid}/", {
            "first_name": "Updated", "last_name": "Doe",
            "date_of_birth": "1990-05-15", "gender": "Female",
        }, **self.headers)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data["first_name"], "Updated")

    def test_delete_patient(self):
        resp = self._make_patient()
        pid = resp.data["id"]
        resp2 = self.client.delete(f"/api/patients/{pid}/", **self.headers)
        self.assertEqual(resp2.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Patient.objects.filter(pk=pid).exists())


class DoctorTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.headers = auth_header(self.user)

    def _make_doctor(self):
        return self.client.post("/api/doctors/", {
            "name": "Dr. Smith", "specialization": "Cardiology",
            "email": "smith@clinic.com", "phone": "555-0100",
        }, **self.headers)

    def test_doctor_crud(self):
        resp = self._make_doctor()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        did = resp.data["id"]

        resp2 = self.client.get(f"/api/doctors/{did}/", **self.headers)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)

        resp3 = self.client.put(f"/api/doctors/{did}/", {
            "name": "Dr. Smith", "specialization": "Neurology",
            "email": "smith@clinic.com", "phone": "555-0100",
        }, **self.headers)
        self.assertEqual(resp3.status_code, status.HTTP_200_OK)
        self.assertEqual(resp3.data["specialization"], "Neurology")

        resp4 = self.client.delete(f"/api/doctors/{did}/", **self.headers)
        self.assertEqual(resp4.status_code, status.HTTP_204_NO_CONTENT)


class MappingTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.other = make_user("other2@example.com", name="Other2")
        self.headers = auth_header(self.user)
        self.other_headers = auth_header(self.other)

        self.patient = Patient.objects.create(
            first_name="Test", last_name="Patient",
            date_of_birth="1985-03-20", gender="Male",
            created_by=self.user,
        )
        self.other_patient = Patient.objects.create(
            first_name="Other", last_name="Patient",
            date_of_birth="1990-01-01", gender="Female",
            created_by=self.other,
        )
        self.doctor = Doctor.objects.create(
            name="Dr. Jones", specialization="Dermatology",
            email="jones@clinic.com", phone="555-0200",
        )

    def test_assign_doctor(self):
        resp = self.client.post("/api/mappings/", {
            "patient": self.patient.id, "doctor": self.doctor.id,
        }, **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_duplicate_assignment_rejected(self):
        PatientDoctorMapping.objects.create(patient=self.patient, doctor=self.doctor)
        resp = self.client.post("/api/mappings/", {
            "patient": self.patient.id, "doctor": self.doctor.id,
        }, **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_assign_to_other_users_patient_denied(self):
        resp = self.client.post("/api/mappings/", {
            "patient": self.other_patient.id, "doctor": self.doctor.id,
        }, **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_mappings_by_patient(self):
        PatientDoctorMapping.objects.create(patient=self.patient, doctor=self.doctor)
        resp = self.client.get(f"/api/mappings/{self.patient.id}/", **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_get_mappings_other_patient_denied(self):
        resp = self.client.get(f"/api/mappings/{self.other_patient.id}/", **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_mapping_leaves_records(self):
        mapping = PatientDoctorMapping.objects.create(patient=self.patient, doctor=self.doctor)
        resp = self.client.delete(f"/api/mappings/delete/{mapping.id}/", **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(Patient.objects.filter(pk=self.patient.id).exists())
        self.assertTrue(Doctor.objects.filter(pk=self.doctor.id).exists())
        self.assertFalse(PatientDoctorMapping.objects.filter(pk=mapping.id).exists())

    def test_invalid_patient_id(self):
        resp = self.client.post("/api/mappings/", {
            "patient": 99999, "doctor": self.doctor.id,
        }, **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
