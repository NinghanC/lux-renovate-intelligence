import pytest

from app.services.evidence_metadata import evidence_role_for_document_type, infer_upload_subtype


@pytest.mark.parametrize(
    ("filename", "text", "expected"),
    [
        ("environment.md", "Commodo-incommodo environmental authorization conditions.", "environmental_authorization"),
        ("classified.txt", "Classified establishment exploitation permit conditions.", "classified_establishment_document"),
        ("asbestos.txt", "Asbestos and pollutant inventory before works.", "asbestos_pollutant_document"),
        ("commissioning.txt", "HVAC commissioning report and functional test results.", "commissioning_report"),
        ("scan.txt", "3D scan and measurement survey for the building.", "survey_scan_document"),
        ("claim.txt", "Expertise note for defect and damage claim.", "expertise_claim_document"),
    ],
)
def test_mission_upload_subtypes_are_inferred(filename: str, text: str, expected: str):
    assert infer_upload_subtype(filename, text) == expected


@pytest.mark.parametrize(
    ("source_subtype", "expected_role"),
    [
        ("environmental_authorization", "planning_context"),
        ("classified_establishment_document", "planning_context"),
        ("asbestos_pollutant_document", "hazardous_material_context"),
        ("commissioning_report", "maintenance_context"),
        ("hvac_mep_document", "maintenance_context"),
        ("comfort_energy_document", "energy_context"),
        ("survey_scan_document", "building_record"),
        ("expertise_claim_document", "condition_observation"),
    ],
)
def test_mission_upload_subtypes_map_to_evidence_roles(source_subtype: str, expected_role: str):
    assert evidence_role_for_document_type("uploaded", source_subtype) == expected_role
